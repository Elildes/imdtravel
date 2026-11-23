"""Endpoints do IMDTravel."""

from flask import Blueprint, current_app, jsonify


bp = Blueprint("imdtravel", __name__)


@bp.get("/sales")
def sales():
    return jsonify(current_app.extensions["store"].list_sales())
