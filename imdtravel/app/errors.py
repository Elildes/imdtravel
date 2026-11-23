"""Exceções de domínio e sua tradução para respostas HTTP.

Atenção: aqui uma falha de dependência vira 500 e nada mais. Nenhum handler
transforma erro em sucesso (requisito da Parte 1).
"""
from flask import jsonify
from werkzeug.exceptions import HTTPException

from .logging_json import log_event


class AppError(Exception):
    status = 500
    code = "internal-error"


class InvalidRequest(AppError):
    status = 400
    code = "invalid-request"


class NotFound(AppError):
    status = 404
    code = "not-found"


class SoldOut(AppError):
    status = 409
    code = "sold-out"


class DependencyError(AppError):
    """Uma dependência (AirlinesHub, Exchange ou Fidelity) falhou."""

    status = 500
    code = "dependency-failure"

    def __init__(self, service: str, detail: str = ""):
        super().__init__(f"{service}: {detail}")
        self.service = service
        self.detail = detail


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def _app_error(exc):
        body = {"error": exc.code}
        if isinstance(exc, DependencyError):
            body["service"] = exc.service
        return jsonify(body), exc.status

    @app.errorhandler(HTTPException)
    def _http_error(exc):
        return jsonify({"error": exc.name.lower().replace(" ", "-")}), exc.code

    @app.errorhandler(Exception)
    def _unexpected(exc):
        log_event("erro.inesperado", error=type(exc).__name__, detail=str(exc))
        return jsonify({"error": "internal-error"}), 500
