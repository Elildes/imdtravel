# Roteiro de observação — resumo

Execução de **23/11/2026** (22:59 a 23:03 UTC), com `tests/roteiro_observacao.sh`, sobre o sistema subido
com `docker-compose.yml` (nosso IMDTravel + imagens `baseline` de AirlinesHub, Exchange e Fidelity).
As falhas foram provocadas parando (`docker compose stop`) ou congelando (`docker compose pause`) um
container. Os números abaixo são os **observados**, copiados dos arquivos de cada cenário.

| Cenário | Status | Tempo até a resposta | Assentos (antes → depois) | Linhas em `/sales` (antes → depois) | Evidência |
|---|---|---|---|---|---|
| A — Fidelity parado | 500 `dependency-failure` (fidelity) | 0,77 s | 20 → **19** | 93 → 93 | [A](A-fidelity-parado.txt) |
| B — Fidelity congelado | nenhuma: o cliente desistiu | 120 s (limite do `curl`) | 19 → **18** | 93 → 93 durante o pause; **94** depois do unpause | [B](B-fidelity-congelado.txt) |
| C — Exchange parado | 500 `dependency-failure` (exchange) | 0,07 s | 20 → 20 | 94 → 94 | [C](C-exchange-parado.txt) |
| D — AirlinesHub parado | 500 `dependency-failure` (airlineshub) | 0,03 s | estoque volta a 20 ao reiniciar | 94 → 94 | [D](D-airlineshub-parado.txt) |

| Cenário | Resultado | Evidência |
|---|---|---|
| E — Conferência `/sales` × estoque | 3 compras ok + 1 com o Fidelity parado no mesmo par: o AirlinesHub vendeu **4** assentos, o `/sales` registrou **3** | [E](E-conferencia-sales-estoque.txt) |
| F — Idade da taxa | duas compras com 15 s de intervalo: `rate` 5,5077 → 5,5124 e `rateAsOf` 23:02:30 → 23:02:40 | [F](F-idade-da-taxa.txt) |

## Conclusões

- **Timeout padrão observado: nenhum.** No cenário B, a chamada ao Fidelity congelado ficou aberta por
  **119,7 s** (log `chamada.saida`, `ms: 119716.1`). Ela só terminou porque o Fidelity voltou. O IMDTravel
  não desiste sozinho: nem o `requests` (sem `timeout=`) nem o Gunicorn (`--timeout 0`) cortam a chamada.
- **Parado não é o mesmo que congelado.** Com o container parado (A, C, D), o nome do serviço some do DNS
  interno do Docker e a chamada falha em menos de 1 s. Com o container congelado (B), a conexão é aceita e a
  resposta nunca vem, e a compra fica presa pelo tempo que a dependência demorar.
- **O assento é consumido quando a falha vem do Fidelity.** No cenário A, o `/sell` (passo 3, irreversível)
  já tinha rodado quando o `/bonus` (passo 4) falhou: estoque 20 → 19, resposta 500, nenhuma linha em
  `/sales`. É o defeito de projeto que a especificação pede para observar.
- **Falhas antes do passo 3 não perdem assento.** Com Exchange (C) ou AirlinesHub (D) fora do ar, a compra
  falha antes do `/sell` e o estoque fica intacto.
- **Venda fantasma (cenário E).** O AirlinesHub vendeu 4 assentos e o `/sales` registrou 3. A diferença é a
  compra que falhou no Fidelity: o assento saiu do estoque, o cliente recebeu 500 e não há registro dela.
- **Venda que o cliente não vê (cenário B).** O cliente desistiu depois de 120 s, sem resposta. Quando o
  Fidelity voltou, o IMDTravel terminou a compra, gravou a venda (`/sales` 93 → 94) e respondeu 201 para
  uma conexão que já não existia. Do ponto de vista do cliente, a compra falhou; no sistema, ela aconteceu.
- **Estado em memória.** Ao reiniciar, o AirlinesHub recria o catálogo com 20 assentos por par (cenário D),
  enquanto o `/sales` do IMDTravel, que está num volume, mantém o histórico. Depois de um reinício, `/sales`
  e estoque deixam de ser comparáveis.
- **A taxa envelhece a cada 10 s (cenário F).** Duas compras com 15 s de intervalo usaram taxas diferentes,
  com `rateAsOf` 10 s distantes.

Esses números são a linha de base da Parte 2: o mesmo roteiro deve ser rodado na versão com tolerância a
falhas, para comparar.
