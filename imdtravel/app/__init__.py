"""IMDTravel - orquestrador de compra de passagens (Parte 1, BASELINE)."""
import time

from flask import Flask

from .config import Config
from .errors import register_error_handlers
from .logging_json import setup_logging
from .correlation import register_correlation
from .clients import Dependencies
from .storage import SalesStore
from .routes import bp


def create_app(config: Config | None = None) -> Flask:
    config = config or Config.from_env()
    setup_logging()

    app = Flask(__name__)
    app.json.sort_keys = False
    app.config["IMD"] = config
    app.config["STARTED_AT"] = time.monotonic()

    store = SalesStore(config.sales_dir)
    store.init()
    app.extensions["store"] = store
    app.extensions["deps"] = Dependencies(config)

    register_correlation(app)
    register_error_handlers(app)
    app.register_blueprint(bp)
    return app
