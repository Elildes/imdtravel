"""Configuração do IMDTravel, lida das variáveis de ambiente."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    port: int
    sales_dir: str
    airlineshub_url: str
    exchange_url: str
    fidelity_url: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            port=int(os.environ.get("PORT", "8080")),
            sales_dir=os.environ.get("SALES_DIR", "/data"),
            airlineshub_url=os.environ.get("AIRLINESHUB_URL", "http://airlineshub:8080").rstrip("/"),
            exchange_url=os.environ.get("EXCHANGE_URL", "http://exchange:8080").rstrip("/"),
            fidelity_url=os.environ.get("FIDELITY_URL", "http://fidelity:8080").rstrip("/"),
        )
