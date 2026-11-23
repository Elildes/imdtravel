"""Registro local das vendas concluídas (SQLite em um volume nomeado)."""
import os
import sqlite3
from contextlib import closing


class SalesStore:
    def __init__(self, directory: str):
        self.directory = directory
        self.path = os.path.join(directory, "sales.db")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        os.makedirs(self.directory, exist_ok=True)
        with closing(self._conn()) as conn, conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS sales (
                       id             INTEGER PRIMARY KEY AUTOINCREMENT,
                       correlation_id TEXT NOT NULL,
                       transaction_id TEXT NOT NULL,
                       flight         TEXT NOT NULL,
                       day            TEXT NOT NULL,
                       user           TEXT NOT NULL,
                       value_usd      REAL NOT NULL,
                       value_brl      REAL NOT NULL,
                       ts             TEXT NOT NULL
                   )"""
            )

    def insert_sale(self, correlation_id, transaction_id, flight, day, user,
                    value_usd, value_brl, ts) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute(
                """INSERT INTO sales (correlation_id, transaction_id, flight, day, user,
                                      value_usd, value_brl, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (correlation_id, transaction_id, flight, day, user, value_usd, value_brl, ts),
            )

    def list_sales(self) -> list[dict]:
        with closing(self._conn()) as conn:
            rows = conn.execute("SELECT * FROM sales ORDER BY id").fetchall()
        return [
            {
                "correlationId": r["correlation_id"],
                "transactionId": r["transaction_id"],
                "flight": r["flight"],
                "day": r["day"],
                "user": r["user"],
                "valueUSD": r["value_usd"],
                "valueBRL": r["value_brl"],
                "ts": r["ts"],
            }
            for r in rows
        ]

    def ping(self) -> None:
        """Verificação real para o /health: o volume é gravável e o banco responde."""
        if not os.access(self.directory, os.W_OK):
            raise RuntimeError(f"diretório {self.directory} não é gravável")
        with closing(self._conn()) as conn:
            conn.execute("SELECT 1 FROM sales LIMIT 1").fetchall()
