"""X-Correlation-Id: gera (ou aproveita) o id e registra início e fim da requisição."""
import time
import uuid

from flask import g, request

from .logging_json import log_event

HEADER = "X-Correlation-Id"


def register_correlation(app):
    @app.before_request
    def _antes():
        g.cid = request.headers.get(HEADER) or str(uuid.uuid4())
        g.t0 = time.perf_counter()
        if request.path != "/health":
            log_event("requisicao.recebida", method=request.method, path=request.path)

    @app.after_request
    def _depois(resp):
        cid = getattr(g, "cid", None)
        if cid:
            resp.headers[HEADER] = cid
        ms = (time.perf_counter() - getattr(g, "t0", time.perf_counter())) * 1000
        # /health só entra no log quando a resposta não é 200 (evita afogar o resto)
        if request.path != "/health" or resp.status_code != 200:
            log_event(
                "resposta.enviada",
                ms=ms,
                method=request.method,
                path=request.path,
                status=resp.status_code,
            )
        return resp
