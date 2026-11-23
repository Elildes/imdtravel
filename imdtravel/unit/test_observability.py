from conftest import PEDIDO


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    corpo = r.get_json()
    assert corpo["status"] == "ok" and isinstance(corpo["uptimeS"], int)


def test_health_down_quando_o_armazenamento_falha(client, app):
    def quebrado():
        raise RuntimeError("volume sem permissão")

    app.extensions["store"].ping = quebrado
    r = client.get("/health")
    assert r.status_code == 503
    assert r.get_json() == {"status": "down", "reason": "volume sem permissão"}


def test_logs_json_com_campos_minimos(client, deps_ok, logs):
    client.post("/buyTicket", json=PEDIDO, headers={"X-Correlation-Id": "cid-log"})
    assert logs
    for linha in logs:
        assert {"ts", "svc", "cid", "event", "ms"} <= set(linha)
        assert linha["svc"] == "imdtravel"
        assert linha["cid"] == "cid-log"          # cid em TODA linha
    eventos = [linha["event"] for linha in logs]
    assert eventos[0] == "requisicao.recebida"
    assert eventos.count("chamada.saida") == 4
    assert eventos[-1] == "resposta.enviada"
    assert logs[-1]["status"] == 201


def test_health_200_nao_polui_o_log(client, logs):
    client.get("/health")
    assert logs == []


def test_rota_inexistente_404_json(client):
    r = client.get("/nao-existe")
    assert r.status_code == 404
    assert r.get_json() == {"error": "not-found"}
