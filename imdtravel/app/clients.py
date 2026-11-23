"""Chamadas HTTP às dependências.

PARTE 1 - SEM TOLERÂNCIA A FALHAS (requisito, não descuido):
  * nenhuma chamada recebe `timeout=`; vale o padrão da biblioteca (esperar sem limite);
  * nenhuma retentativa, cache, valor padrão ou caminho alternativo;
  * qualquer falha vira DependencyError, que o handler global transforma em 500.
"""
import time

import requests

from .config import Config
from .errors import DependencyError, NotFound, SoldOut
from .logging_json import log_event


class Dependencies:
    def __init__(self, config: Config):
        self.airlineshub = config.airlineshub_url
        self.exchange = config.exchange_url
        self.fidelity = config.fidelity_url

    # ------------------------------------------------------------ infraestrutura
    def _request(self, service: str, method: str, url: str, cid: str, **kwargs):
        headers = {"X-Correlation-Id": cid}
        inicio = time.perf_counter()
        try:
            # Sem `timeout`: de propósito (ver docstring do módulo).
            resp = requests.request(method, url, headers=headers, **kwargs)
        except requests.RequestException as exc:
            log_event("chamada.falhou", cid=cid, ms=(time.perf_counter() - inicio) * 1000,
                      dependency=service, method=method, url=url, error=type(exc).__name__)
            raise DependencyError(service, f"{type(exc).__name__}: {exc}") from exc
        log_event("chamada.saida", cid=cid, ms=(time.perf_counter() - inicio) * 1000,
                  dependency=service, method=method, url=url, status=resp.status_code)
        return resp

    @staticmethod
    def _json(service: str, resp, *campos):
        try:
            corpo = resp.json()
        except ValueError as exc:
            raise DependencyError(service, "resposta não é JSON") from exc
        if not isinstance(corpo, dict) or any(c not in corpo for c in campos):
            raise DependencyError(service, f"resposta sem os campos esperados {campos}")
        return corpo

    # ------------------------------------------------------------ as 4 chamadas
    def get_flight(self, flight: str, day: str, cid: str) -> dict:
        """Requisição 1: GET /flight no AirlinesHub."""
        resp = self._request("airlineshub", "GET", f"{self.airlineshub}/flight", cid,
                             params={"flight": flight, "day": day})
        if resp.status_code == 404:
            raise NotFound()
        if resp.status_code != 200:
            raise DependencyError("airlineshub", f"GET /flight devolveu {resp.status_code}")
        return self._json("airlineshub", resp, "priceUSD")

    def get_rate(self, cid: str) -> dict:
        """Requisição 2: GET /convert no Exchange."""
        resp = self._request("exchange", "GET", f"{self.exchange}/convert", cid)
        if resp.status_code != 200:
            raise DependencyError("exchange", f"GET /convert devolveu {resp.status_code}")
        return self._json("exchange", resp, "rate", "asOf")

    def sell(self, flight: str, day: str, cid: str) -> dict:
        """Requisição 3: POST /sell no AirlinesHub (passo irreversível: consome o assento)."""
        resp = self._request("airlineshub", "POST", f"{self.airlineshub}/sell", cid,
                             json={"flight": flight, "day": day})
        if resp.status_code == 409:
            raise SoldOut()
        if resp.status_code not in (200, 201):
            raise DependencyError("airlineshub", f"POST /sell devolveu {resp.status_code}")
        return self._json("airlineshub", resp, "transactionId")

    def add_bonus(self, user: str, bonus: int, cid: str) -> dict:
        """Requisição 4: POST /bonus no Fidelity (no caminho crítico, de propósito)."""
        resp = self._request("fidelity", "POST", f"{self.fidelity}/bonus", cid,
                             json={"user": user, "bonus": bonus})
        if resp.status_code not in (200, 201):
            raise DependencyError("fidelity", f"POST /bonus devolveu {resp.status_code}")
        return self._json("fidelity", resp, "totalPoints")
