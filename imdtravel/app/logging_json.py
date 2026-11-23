"""Log estruturado: um objeto JSON por linha na saída padrão."""
import json
import logging
import sys
from datetime import datetime, timezone

from flask import g, has_request_context

SVC = "imdtravel"
_logger = logging.getLogger("imdtravel.json")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(record.msg, ensure_ascii=False, default=str)


def setup_logging() -> None:
    if _logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def current_cid():
    return getattr(g, "cid", None) if has_request_context() else None


def log_event(event: str, cid: str | None = None, ms: float = 0, **campos) -> None:
    """Escreve uma linha de log com os campos mínimos: ts, svc, cid, event e ms."""
    entrada = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "svc": SVC,
        "cid": cid or current_cid(),
        "event": event,
        "ms": round(ms, 1),
    }
    entrada.update(campos)
    _logger.info(entrada)
