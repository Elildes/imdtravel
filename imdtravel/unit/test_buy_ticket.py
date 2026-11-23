import pytest
import requests

from conftest import EXC, FID, HUB, PEDIDO


def test_compra_ok(client, deps_ok):
    r = client.post("/buyTicket", json=PEDIDO, headers={"X-Correlation-Id": "cid-1"})
    assert r.status_code == 201
    corpo = r.get_json()
    assert set(corpo) == {"transactionId", "flight", "day", "user", "valueUSD",
                          "valueBRL", "rate", "rateAsOf", "bonus"}
    assert corpo["valueUSD"] == 350.5
    assert corpo["rate"] == 5.5
    assert corpo["valueBRL"] == 1927.75      # 350.50 x 5.50
    assert corpo["bonus"] == 350             # parte inteira do preço
    assert corpo["transactionId"] == "TX-1"
    assert r.headers["X-Correlation-Id"] == "cid-1"


def test_preco_sai_com_o_mesmo_texto_do_airlineshub(client, deps_ok):
    """O testes.sh compara o texto: 350.50 tem de sair 350.50, e não 350.5."""
    r = client.post("/buyTicket", json=PEDIDO)
    assert '"valueUSD":350.50' in r.get_data(as_text=True)


def test_valor_em_reais_arredonda_em_duas_casas(client, deps_ok):
    deps_ok.get(f"{EXC}/convert", json={"rate": 5.4757, "asOf": "2026-12-01T10:00:00Z"})
    corpo = client.post("/buyTicket", json=PEDIDO).get_json()
    assert str(corpo["valueBRL"]) == "1919.23"   # 350.50 x 5.4757 = 1919.232...


def test_as_quatro_chamadas_na_ordem_com_o_mesmo_cid(client, deps_ok):
    client.post("/buyTicket", json=PEDIDO, headers={"X-Correlation-Id": "cid-2"})
    historico = [(h.method, h.path) for h in deps_ok.request_history]
    assert historico == [("GET", "/flight"), ("GET", "/convert"),
                         ("POST", "/sell"), ("POST", "/bonus")]
    assert all(h.headers["X-Correlation-Id"] == "cid-2" for h in deps_ok.request_history)


def test_bonus_enviado_ao_fidelity(client, deps_ok):
    client.post("/buyTicket", json=PEDIDO)
    bonus = [h for h in deps_ok.request_history if h.path == "/bonus"][0]
    assert bonus.json() == {"user": "ana", "bonus": 350}


def test_nenhuma_chamada_tem_timeout(client, deps_ok):
    """Requisito da Parte 1: sem timeout (o padrão do requests é None)."""
    client.post("/buyTicket", json=PEDIDO)
    assert all(h.timeout is None for h in deps_ok.request_history)


def test_cid_gerado_quando_ausente(client, deps_ok):
    r = client.post("/buyTicket", json=PEDIDO)
    cid = r.headers["X-Correlation-Id"]
    assert cid
    assert client.get("/sales").get_json()[0]["correlationId"] == cid


def test_compra_gravada_em_sales(client, deps_ok):
    client.post("/buyTicket", json=PEDIDO, headers={"X-Correlation-Id": "cid-3"})
    linhas = client.get("/sales").get_json()
    assert len(linhas) == 1
    linha = linhas[0]
    assert linha["correlationId"] == "cid-3"
    assert linha["transactionId"] == "TX-1"
    assert (linha["flight"], linha["day"], linha["user"]) == ("IMD100", "2026-12-01", "ana")
    assert linha["valueUSD"] == 350.5 and linha["valueBRL"] == 1927.75 and linha["ts"]


@pytest.mark.parametrize("corpo", [
    {"flight": "IMD100", "user": "ana"},                       # sem day
    {"flight": "IMD100", "day": "2026-12-01", "user": ""},     # user vazio
    {"flight": "IMD100", "day": "2026-12-01", "user": "   "},  # user só com espaços
    {"flight": 10, "day": "2026-12-01", "user": "ana"},        # tipo errado
    ["não", "é", "objeto"],
])
def test_pedido_invalido_400(client, deps_ok, corpo):
    r = client.post("/buyTicket", json=corpo)
    assert r.status_code == 400
    assert r.get_json() == {"error": "invalid-request"}
    assert deps_ok.call_count == 0               # nada foi chamado
    assert client.get("/sales").get_json() == []


def test_json_malformado_400(client, deps_ok):
    r = client.post("/buyTicket", data="{malformado", content_type="application/json")
    assert r.status_code == 400
    assert deps_ok.call_count == 0


def test_voo_inexistente_404(client, deps_ok):
    deps_ok.get(f"{HUB}/flight", status_code=404, json={"error": "not-found"})
    r = client.post("/buyTicket", json=PEDIDO)
    assert r.status_code == 404
    assert r.get_json() == {"error": "not-found"}
    assert not any(h.path == "/sell" for h in deps_ok.request_history)


def test_esgotado_409_sem_bonus(client, deps_ok):
    deps_ok.post(f"{HUB}/sell", status_code=409, json={"error": "sold-out"})
    r = client.post("/buyTicket", json=PEDIDO)
    assert r.status_code == 409
    assert r.get_json() == {"error": "sold-out"}
    assert not any(h.path == "/bonus" for h in deps_ok.request_history)
    assert client.get("/sales").get_json() == []


def test_fidelity_com_erro_derruba_a_compra_mas_o_assento_foi_vendido(client, deps_ok):
    """O defeito de projeto que a Parte 1 quer evidenciar."""
    deps_ok.post(f"{FID}/bonus", status_code=500)
    r = client.post("/buyTicket", json=PEDIDO)
    assert r.status_code == 500
    assert r.get_json() == {"error": "dependency-failure", "service": "fidelity"}
    assert any(h.path == "/sell" for h in deps_ok.request_history)   # assento consumido
    assert client.get("/sales").get_json() == []                    # e sem registro


def test_exchange_fora_do_ar_500_antes_de_vender(client, deps_ok):
    deps_ok.get(f"{EXC}/convert", exc=requests.ConnectionError("recusada"))
    r = client.post("/buyTicket", json=PEDIDO)
    assert r.status_code == 500
    assert r.get_json()["error"] == "dependency-failure"
    assert not any(h.path == "/sell" for h in deps_ok.request_history)


def test_resposta_que_nao_e_json_vira_500(client, deps_ok):
    deps_ok.get(f"{EXC}/convert", text="<html>erro</html>")
    r = client.post("/buyTicket", json=PEDIDO)
    assert r.status_code == 500
    assert r.get_json() == {"error": "dependency-failure", "service": "exchange"}


def test_nenhuma_retentativa(client, deps_ok):
    deps_ok.post(f"{FID}/bonus", status_code=500)
    client.post("/buyTicket", json=PEDIDO)
    assert sum(1 for h in deps_ok.request_history if h.path == "/bonus") == 1
