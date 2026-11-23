#!/usr/bin/env bash
#
# roteiro_observacao.sh — provoca falhas nas dependências (parando ou congelando containers)
# e registra o que o IMDTravel faz: status, tempo até a resposta, estoque e /sales.
# Nada aqui é corrigido: só se observa. É a linha de base para comparar com a Parte 2.
#
# Uso (na raiz do repositório, com o sistema no ar):   tests/roteiro_observacao.sh
# Gera um arquivo por cenário em tests/evidencias/ (A a F).
# Requer: docker compose, curl, jq.   Leva ~3 minutos (o cenário B espera 120 s de propósito).

set -u
cd "$(dirname "$0")/.."
BASE="http://localhost:${IMDTRAVEL_HOST_PORT:-8080}"
EV="tests/evidencias"
mkdir -p "$EV"

assentos() { docker compose exec -T airlineshub curl -s "localhost:8080/flight?flight=$1&day=$2" | jq -r .seatsAvailable; }
vendas()   { curl -s "$BASE/sales" | jq length; }
# compra <cid> <voo> <dia> <usuário> [max-time] — imprime "status=… tempo=…s" e o corpo
compra() {
    curl -s --max-time "${5:-600}" -w '\nstatus=%{http_code} tempo=%{time_total}s\n' \
         -H 'Content-Type: application/json' -H "X-Correlation-Id: $1" \
         -d "{\"flight\":\"$2\",\"day\":\"$3\",\"user\":\"$4\"}" "$BASE/buyTicket"
}
log_cid() { docker compose logs --no-log-prefix imdtravel | grep "\"$1\"" | jq -c '{ts,event,ms,dependency,status,error}'; }
sadio()   { docker compose up -d --wait >/dev/null 2>&1; }
titulo()  { echo; echo "=== $*"; echo "data: $(date -u +%Y-%m-%dT%H:%M:%SZ)"; }

sadio

# ---------------------------------------------------------------- A
{
  titulo "Cenário A — Fidelity parado (falha DEPOIS do passo irreversível /sell)"
  echo "ANTES:  assentos IMD200/2026-12-03 = $(assentos IMD200 2026-12-03)   linhas em /sales = $(vendas)"
  docker compose stop fidelity >/dev/null 2>&1
  compra obs-a1 IMD200 2026-12-03 obs-bia
  docker compose start fidelity >/dev/null 2>&1; sadio
  echo "DEPOIS: assentos IMD200/2026-12-03 = $(assentos IMD200 2026-12-03)   linhas em /sales = $(vendas)"
  echo "--- log do IMDTravel (cid obs-a1)"; log_cid obs-a1
} 2>&1 | tee "$EV/A-fidelity-parado.txt"

# ---------------------------------------------------------------- B
{
  titulo "Cenário B — Fidelity congelado (docker pause: a conexão abre, a resposta não vem)"
  echo "ANTES:  assentos IMD200/2026-12-03 = $(assentos IMD200 2026-12-03)   linhas em /sales = $(vendas)"
  docker compose pause fidelity >/dev/null 2>&1
  echo "--- o cliente (curl) desiste em 120 s; o IMDTravel não tem timeout"
  compra obs-b1 IMD200 2026-12-03 obs-caio 120
  echo "--- log do IMDTravel até aqui (cid obs-b1): a chamada ao Fidelity ainda não terminou"; log_cid obs-b1
  echo "--- depois de 120 s, durante o pause: assentos = $(assentos IMD200 2026-12-03)   linhas em /sales = $(vendas)"
  docker compose unpause fidelity >/dev/null 2>&1
  sleep 5
  echo "--- 5 s depois do unpause"
  echo "DEPOIS: assentos IMD200/2026-12-03 = $(assentos IMD200 2026-12-03)   linhas em /sales = $(vendas)"
  echo "--- log do IMDTravel (cid obs-b1)"; log_cid obs-b1
} 2>&1 | tee "$EV/B-fidelity-congelado.txt"

# ---------------------------------------------------------------- C
{
  titulo "Cenário C — Exchange parado (falha ANTES do passo irreversível)"
  echo "ANTES:  assentos IMD200/2026-12-04 = $(assentos IMD200 2026-12-04)   linhas em /sales = $(vendas)"
  docker compose stop exchange >/dev/null 2>&1
  compra obs-c1 IMD200 2026-12-04 obs-dani
  docker compose start exchange >/dev/null 2>&1; sadio
  echo "DEPOIS: assentos IMD200/2026-12-04 = $(assentos IMD200 2026-12-04)   linhas em /sales = $(vendas)"
  echo "--- log do IMDTravel (cid obs-c1)"; log_cid obs-c1
} 2>&1 | tee "$EV/C-exchange-parado.txt"

# ---------------------------------------------------------------- D
{
  titulo "Cenário D — AirlinesHub parado (falha na primeira chamada)"
  echo "ANTES:  linhas em /sales = $(vendas)"
  docker compose stop airlineshub >/dev/null 2>&1
  compra obs-d1 IMD200 2026-12-04 obs-edu
  docker compose start airlineshub >/dev/null 2>&1; sadio
  echo "DEPOIS: linhas em /sales = $(vendas)"
  echo "--- o AirlinesHub guarda o estoque em memória: ao voltar, o catálogo recomeça com 20 assentos por par"
  echo "assentos IMD200/2026-12-03 depois do restart = $(assentos IMD200 2026-12-03)  (antes do restart havia vendas nesse par)"
  echo "--- log do IMDTravel (cid obs-d1)"; log_cid obs-d1
} 2>&1 | tee "$EV/D-airlineshub-parado.txt"

# ---------------------------------------------------------------- E
{
  titulo "Cenário E — Conferência entre /sales e o estoque real (catálogo recém-reiniciado no cenário D)"
  echo "ANTES:  assentos IMD300/2026-12-06 = $(assentos IMD300 2026-12-06)"
  for u in a b c; do compra "obs-e-$u" IMD300 2026-12-06 "obs-e-$u" >/dev/null; done
  docker compose stop fidelity >/dev/null 2>&1
  compra obs-e-x IMD300 2026-12-06 obs-e-falha | tail -1
  docker compose start fidelity >/dev/null 2>&1; sadio
  disp="$(assentos IMD300 2026-12-06)"
  echo "assentos vendidos pelo AirlinesHub (20 - $disp): $((20 - disp))"
  echo "linhas em /sales para o par:  $(curl -s "$BASE/sales" | jq '[.[]|select(.flight=="IMD300" and .day=="2026-12-06" and (.correlationId|startswith("obs-e")))]|length')"
} 2>&1 | tee "$EV/E-conferencia-sales-estoque.txt"

# ---------------------------------------------------------------- F
{
  titulo "Cenário F — Idade da taxa de câmbio (o Exchange atualiza a cada 10 s)"
  compra obs-f1 IMD100 2026-12-05 obs-f | head -1 | jq -c '{rate,rateAsOf}'
  sleep 15
  compra obs-f2 IMD100 2026-12-05 obs-f | head -1 | jq -c '{rate,rateAsOf}'
} 2>&1 | tee "$EV/F-idade-da-taxa.txt"

echo; echo "Evidências gravadas em $EV/"
