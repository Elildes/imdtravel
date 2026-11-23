"""Endpoints do IMDTravel."""
import time

from flask import Blueprint, current_app, jsonify


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
