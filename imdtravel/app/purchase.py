"""Orquestração da compra: as quatro chamadas, na ordem obrigatória.

PARTE 1 - SEM TOLERÂNCIA A FALHAS: qualquer exceção de uma chamada sobe sem tratamento
e vira 500 no handler global. Se o /bonus falhar depois do /sell, o assento já foi
consumido e nada é gravado em /sales (o defeito de projeto que a Parte 1 quer observar).
"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal


def buy_ticket(deps, store, flight: str, day: str, user: str, cid: str) -> dict:
    # 1. consulta o voo (reversível)
    voo = deps.get_flight(flight, day, cid)
    price_usd = Decimal(str(voo["priceUSD"]))       # str(): aceita Decimal ou float

    # 2. obtém a taxa de câmbio (reversível)
    cambio = deps.get_rate(cid)
    rate = Decimal(str(cambio["rate"]))

    # 3. efetiva a venda (IRREVERSÍVEL: o assento sai do estoque)
    venda = deps.sell(flight, day, cid)

    # 4. credita o bônus: parte inteira do preço em dólar
    bonus = int(price_usd)
    deps.add_bonus(user, bonus, cid)

    value_brl = (price_usd * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    resultado = {
        "transactionId": venda["transactionId"],
        "flight": flight,
        "day": day,
        "user": user,
        "valueUSD": price_usd,
        "valueBRL": value_brl,
        "rate": rate,
        "rateAsOf": cambio["asOf"],
        "bonus": bonus,
    }

    # Só uma compra concluída (as 4 chamadas) entra no registro local.
    store.insert_sale(
        correlation_id=cid,
        transaction_id=venda["transactionId"],
        flight=flight,
        day=day,
        user=user,
        value_usd=float(price_usd),
        value_brl=float(value_brl),
        ts=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    )
    return resultado
