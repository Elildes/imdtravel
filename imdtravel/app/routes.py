"""Endpoints do IMDTravel."""
import time

from flask import Blueprint, current_app, g, jsonify, request

from .errors import InvalidRequest
from .purchase import buy_ticket


bp = Blueprint("imdtravel", __name__)


@bp.get("/sales")
def sales():
    return jsonify(current_app.extensions["store"].list_sales())


@bp.get("/health")
def health():
    try:
        current_app.extensions["store"].ping()
    except Exception as exc:
        return jsonify(status="down", reason=str(exc)), 503
    uptime = int(time.monotonic() - current_app.config["STARTED_AT"])
    return jsonify(status="ok", uptimeS=uptime)


@bp.post("/buyTicket")
def buy_ticket_endpoint():
    # Toda validação acontece ANTES de qualquer chamada externa:
    # pedido inválido nunca consome assento nem cria linha em /sales.
    dados = request.get_json(force=True, silent=True)   # JSON malformado -> None
    if not isinstance(dados, dict):
        raise InvalidRequest()
    flight, day, user = (dados.get(k) for k in ("flight", "day", "user"))
    if not all(isinstance(v, str) and v.strip() for v in (flight, day, user)):
        raise InvalidRequest()

    resultado = buy_ticket(
        current_app.extensions["deps"],
        current_app.extensions["store"],
        flight, day, user, g.cid,
    )
    return jsonify(resultado), 201
