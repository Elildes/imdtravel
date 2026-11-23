import logging

import pytest

from app import create_app
from app.config import Config
from app.logging_json import _logger

HUB = "http://airlineshub:8080"
EXC = "http://exchange:8080"
FID = "http://fidelity:8080"

PEDIDO = {"flight": "IMD100", "day": "2026-12-01", "user": "ana"}


@pytest.fixture
def app(tmp_path):
    cfg = Config(port=8080, sales_dir=str(tmp_path), airlineshub_url=HUB,
                 exchange_url=EXC, fidelity_url=FID)
    return create_app(cfg)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def deps_ok(requests_mock):
    """As quatro dependências respondendo bem (preço 350.50, taxa 5.50)."""
    requests_mock.get(f"{HUB}/flight", text='{"flight":"IMD100","day":"2026-12-01",'
                                            '"priceUSD":350.50,"seatsAvailable":20}')
    requests_mock.get(f"{EXC}/convert", json={"rate": 5.50, "asOf": "2026-12-01T10:00:00Z"})
    requests_mock.post(f"{HUB}/sell", status_code=201,
                       json={"transactionId": "TX-1", "seatsRemaining": 19})
    requests_mock.post(f"{FID}/bonus", status_code=201, json={"user": "ana", "totalPoints": 350})
    return requests_mock


@pytest.fixture
def logs():
    """Coleta as linhas de log estruturado geradas durante o teste."""
    coletadas = []

    class Coletor(logging.Handler):
        def emit(self, record):
            coletadas.append(record.msg)

    handler = Coletor()
    _logger.addHandler(handler)
    yield coletadas
    _logger.removeHandler(handler)
