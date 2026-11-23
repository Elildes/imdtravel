# /// script
# requires-python = ">=3.12"
# dependencies = ["rich==15.0.0"]
# ///
"""Painel local do IMDTravel: faz chamadas ao sistema e mostra o estado dos containers.

Roda fora do Docker, no terminal:   uv run tools/painel.py

- O IMDTravel é chamado pela porta exposta (http://localhost:8080 por padrão; mude com
  IMDTRAVEL=http://host:porta ou IMDTRAVEL_HOST_PORT=9090).
- AirlinesHub, Exchange e Fidelity não têm porta exposta: são consultados com
  `docker compose exec <serviço> curl ...`, igual ao testes.sh.
- COMPOSE_FILE é respeitado (ex.: COMPOSE_FILE=docker-compose.hub.yml).
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta
from pathlib import Path

from rich import box
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

RAIZ = Path(__file__).resolve().parent.parent          # pasta do docker-compose.yml
IMDTRAVEL = os.environ.get(
    "IMDTRAVEL", f"http://localhost:{os.environ.get('IMDTRAVEL_HOST_PORT', '8080')}"
).rstrip("/")
SERVICOS = ["imdtravel", "airlineshub", "exchange", "fidelity"]
VOOS = ["IMD100", "IMD200", "IMD300"]
DIAS = [str(date(2026, 12, 1) + timedelta(days=i)) for i in range(7)]

console = Console()


# ---------------------------------------------------------------- chamadas
def http(method: str, path: str, body: dict | None = None, cid: str | None = None):
    """Chama o IMDTravel. Devolve (status, headers, corpo, ms); status None = sem conexão."""
    dados = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(IMDTRAVEL + path, data=dados, method=method)
    if dados is not None:
        req.add_header("Content-Type", "application/json")
    if cid:
        req.add_header("X-Correlation-Id", cid)
    t0 = time.perf_counter()
    try:
        # timeout grande: na Parte 1 uma compra pode ficar minutos presa (sem timeout no servidor)
        with urllib.request.urlopen(req, timeout=900) as resp:
            status, headers, texto = resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as exc:
        status, headers, texto = exc.code, dict(exc.headers), exc.read().decode()
    except (urllib.error.URLError, OSError) as exc:
        return None, {}, str(getattr(exc, "reason", exc)), (time.perf_counter() - t0) * 1000
    return status, headers, texto, (time.perf_counter() - t0) * 1000


def compose(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], cwd=RAIZ, capture_output=True,
                          text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def interno(servico: str, path: str) -> tuple[bool, str]:
    """GET num serviço da rede interna, via docker compose exec."""
    try:
        r = compose("exec", "-T", servico, "curl", "-s", "-w", "\n%{http_code}",
                    f"localhost:8080{path}")
    except subprocess.TimeoutExpired:
        return False, "sem resposta em 30 s"
    if r.returncode != 0:
        return False, (r.stderr or r.stdout).strip() or "container fora do ar"
    corpo, _, codigo = r.stdout.rpartition("\n")
    return codigo.startswith("2"), corpo


def tenta_json(texto: str):
    try:
        return json.loads(texto)
    except ValueError:
        return None


def cor_status(status) -> str:
    if status is None:
        return "[bold red]sem conexão[/]"
    cor = "green" if status < 300 else "yellow" if status < 500 else "red"
    return f"[bold {cor}]{status}[/]"


def mostra_corpo(texto: str, titulo: str) -> None:
    dado = tenta_json(texto)
    conteudo = JSON.from_data(dado) if dado is not None else (texto or "(vazio)")
    console.print(Panel(conteudo, title=titulo, border_style="cyan"))


# ---------------------------------------------------------------- telas
def estado() -> None:
    with console.status("Consultando os containers..."):
        r = compose("ps", "-a", "--format", "json")
        containers = {}
        for linha in r.stdout.splitlines():
            c = tenta_json(linha)
            if c:
                containers[c["Service"]] = c
        saude = {}
        for s in SERVICOS:
            if s == "imdtravel":
                st, _, texto, _ = http("GET", "/health")
                saude[s] = (st == 200, texto)
            elif s in containers and containers[s].get("State") == "running":
                saude[s] = interno(s, "/health")
            else:
                saude[s] = (False, "container não está rodando")

    if r.returncode != 0:
        console.print(f"[red]docker compose ps falhou:[/] {r.stderr.strip()}")

    t = Table(title="Estado do sistema", box=box.ROUNDED)
    for col in ("Serviço", "Container", "Docker health", "GET /health", "Uptime", "Porta"):
        t.add_column(col)
    for s in SERVICOS:
        c = containers.get(s, {})
        estado_c = c.get("State", "—")
        cor_c = "green" if estado_c == "running" else "red"
        health = c.get("Health") or "—"
        cor_h = {"healthy": "green", "unhealthy": "red", "starting": "yellow"}.get(health, "white")
        ok, texto = saude[s]
        corpo = tenta_json(texto) or {}
        h = "[green]ok[/]" if ok else f"[red]{corpo.get('status', 'falhou')}[/] {corpo.get('reason', texto)[:40]}"
        uptime = f"{corpo['uptimeS']} s" if "uptimeS" in corpo else "—"
        portas = c.get("Publishers") or []
        porta = ", ".join(dict.fromkeys(f"{p['PublishedPort']}→{p['TargetPort']}" for p in portas if p.get("PublishedPort")))
        t.add_row(s, f"[{cor_c}]{estado_c}[/]", f"[{cor_h}]{health}[/]", h, uptime, porta or "interna")
    console.print(t)


def comprar() -> None:
    flight = Prompt.ask("Voo", choices=VOOS + ["outro"], default="IMD100")
    if flight == "outro":
        flight = Prompt.ask("Código do voo")
    day = Prompt.ask("Dia", default=DIAS[0])
    user = Prompt.ask("Usuário", default="ana")
    cid = Prompt.ask("X-Correlation-Id (vazio = gerar)", default="") or f"painel-{uuid.uuid4().hex[:8]}"

    with console.status(f"POST /buyTicket  (cid {cid}) — pode demorar se uma dependência travar..."):
        st, headers, texto, ms = http("POST", "/buyTicket", {"flight": flight, "day": day, "user": user}, cid)
    cid_volta = {k.lower(): v for k, v in headers.items()}.get("x-correlation-id", "—")
    console.print(f"Status {cor_status(st)}   tempo [bold]{ms:.0f} ms[/]   X-Correlation-Id devolvido: {cid_volta}")
    mostra_corpo(texto, "Resposta do POST /buyTicket")
    if st is not None and Prompt.ask("Ver o log dessa compra?", choices=["s", "n"], default="s") == "s":
        logs(cid)


def requisicao_livre() -> None:
    metodo = Prompt.ask("Método", choices=["GET", "POST"], default="GET")
    path = Prompt.ask("Caminho", default="/health")
    body = None
    if metodo == "POST":
        bruto = Prompt.ask("Corpo JSON", default='{"flight":"IMD100","day":"2026-12-01","user":"ana"}')
        body = tenta_json(bruto)
        if body is None:                               # manda o texto cru (ex.: testar JSON malformado)
            req_body = bruto
    with console.status(f"{metodo} {path}..."):
        if metodo == "POST" and body is None:
            st, headers, texto, ms = http_cru(path, req_body)
        else:
            st, headers, texto, ms = http(metodo, path, body)
    console.print(f"Status {cor_status(st)}   tempo [bold]{ms:.0f} ms[/]")
    mostra_corpo(texto, f"{metodo} {path}")


def http_cru(path: str, texto: str):
    req = urllib.request.Request(IMDTRAVEL + path, data=texto.encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            return resp.status, dict(resp.headers), resp.read().decode(), (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode(), (time.perf_counter() - t0) * 1000
    except (urllib.error.URLError, OSError) as exc:
        return None, {}, str(exc), (time.perf_counter() - t0) * 1000


def vendas() -> None:
    st, _, texto, _ = http("GET", "/sales")
    lista = tenta_json(texto)
    if st != 200 or not isinstance(lista, list):
        console.print(f"Status {cor_status(st)}")
        mostra_corpo(texto, "GET /sales")
        return
    t = Table(title=f"GET /sales — {len(lista)} venda(s)", box=box.ROUNDED)
    for col in ("#", "Voo", "Dia", "Usuário", "USD", "BRL", "cid", "transactionId", "Instante"):
        t.add_column(col, overflow="fold")
    for i, v in enumerate(lista[-30:], start=max(1, len(lista) - 29)):
        t.add_row(str(i), v.get("flight"), v.get("day"), v.get("user"), f"{v.get('valueUSD')}",
                  f"{v.get('valueBRL')}", v.get("correlationId"), str(v.get("transactionId"))[:8] + "…",
                  str(v.get("ts")))
    console.print(t)
    if len(lista) > 30:
        console.print("[dim](mostrando as 30 mais recentes)[/]")


def estoque() -> None:
    flight = Prompt.ask("Voo", choices=VOOS + ["todos"], default="todos")
    voos = VOOS if flight == "todos" else [flight]
    t = Table(title="AirlinesHub — assentos livres", box=box.ROUNDED)
    t.add_column("Voo")
    for d in DIAS:
        t.add_column(d[5:], justify="right")
    with console.status("Consultando o AirlinesHub..."):
        for f in voos:
            linha = []
            for d in DIAS:
                ok, texto = interno("airlineshub", f"/flight?flight={f}&day={d}")
                dado = tenta_json(texto) or {}
                n = dado.get("seatsAvailable")
                if n is None:
                    linha.append("[red]erro[/]")
                else:
                    cor = "red" if n == 0 else "yellow" if n < 5 else "green"
                    linha.append(f"[{cor}]{n}[/] [dim]${dado.get('priceUSD')}[/]")
            t.add_row(f, *linha)
    console.print(t)


def cambio() -> None:
    ok, texto = interno("exchange", "/convert")
    mostra_corpo(texto, "Exchange — GET /convert" + ("" if ok else " [red](falhou)[/]"))


def pontos() -> None:
    user = Prompt.ask("Usuário", default="ana")
    ok, texto = interno("fidelity", f"/points?user={user}")
    mostra_corpo(texto, f"Fidelity — pontos de {user}" + ("" if ok else " [red](falhou)[/]"))


def logs(cid: str | None = None) -> None:
    cid = cid or Prompt.ask("cid (X-Correlation-Id) a filtrar")
    with console.status("Lendo os logs dos 4 serviços..."):
        r = compose("logs", "--no-log-prefix", timeout=60)
    linhas = [tenta_json(l) for l in r.stdout.splitlines() if cid in l]
    linhas = sorted((l for l in linhas if l), key=lambda l: str(l.get("ts")))
    if not linhas:
        console.print(f"[yellow]Nenhuma linha de log com o cid {cid}.[/]")
        return
    t = Table(title=f"Logs com cid = {cid}", box=box.ROUNDED)
    for col in ("ts", "svc", "event", "ms", "detalhe"):
        t.add_column(col, overflow="fold")
    for l in linhas:
        extra = {k: v for k, v in l.items() if k not in ("ts", "svc", "cid", "event", "ms") and v is not None}
        t.add_row(str(l.get("ts"))[11:23], l.get("svc"), l.get("event"), str(l.get("ms")),
                  " ".join(f"{k}={v}" for k, v in extra.items()))
    console.print(t)


# ---------------------------------------------------------------- menu
OPCOES = {
    "1": ("Estado dos containers e /health", estado),
    "2": ("Comprar passagem (POST /buyTicket)", comprar),
    "3": ("Vendas registradas (GET /sales)", vendas),
    "4": ("Estoque de assentos (AirlinesHub)", estoque),
    "5": ("Taxa de câmbio (Exchange)", cambio),
    "6": ("Pontos de um usuário (Fidelity)", pontos),
    "7": ("Logs por X-Correlation-Id", logs),
    "8": ("Requisição livre ao IMDTravel", requisicao_livre),
    "0": ("Sair", None),
}


def main() -> None:
    console.print(Panel.fit(f"[bold]IMDTravel — painel local[/]\nIMDTravel em [cyan]{IMDTRAVEL}[/] · "
                            f"compose em [cyan]{RAIZ}[/]", border_style="magenta"))
    estado()
    while True:
        console.print()
        for k, (nome, _) in OPCOES.items():
            console.print(f"  [bold cyan]{k}[/] {nome}")
        escolha = Prompt.ask("Opção", choices=list(OPCOES), default="1", show_choices=False)
        if escolha == "0":
            break
        try:
            OPCOES[escolha][1]()
        except KeyboardInterrupt:
            console.print("\n[yellow]cancelado[/]")
        except Exception as exc:                          # o painel não deve cair por causa de uma tela
            console.print(f"[red]erro no painel:[/] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()
