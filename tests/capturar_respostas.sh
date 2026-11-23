#!/usr/bin/env bash
#
# capturar_respostas.sh — registra, num arquivo, o "formato" das respostas do IMDTravel
# que está no ar, para comparar a nossa implementação com a de referência.
#
# Uso:  tests/capturar_respostas.sh <arquivo-de-saida>
# O que varia a cada execução (transactionId, taxa, valores em reais, datas) não entra
# no arquivo: ficam o status, os nomes dos campos e o corpo dos erros.
#
# Requer: curl, jq.   Porta: IMDTRAVEL_HOST_PORT (padrão 8080).

set -u
BASE="http://localhost:${IMDTRAVEL_HOST_PORT:-8080}"
SAIDA="${1:?informe o arquivo de saída, ex.: tests/referencia/respostas.txt}"
: > "$SAIDA"

# caso <nome> <corpo-json> — faz um POST /buyTicket e anota "nome | status | corpo normalizado"
caso() {
    local tmp status corpo
    tmp="$(mktemp)"
    status="$(curl -s -o "$tmp" -w '%{http_code}' --max-time 60 \
        -H 'Content-Type: application/json' -d "$2" "$BASE/buyTicket")"
    corpo="$(jq -c 'if type=="object" and has("transactionId") then keys else . end' "$tmp" 2>/dev/null \
        || echo '(corpo não é JSON)')"
    echo "$1 | $status | $corpo" >> "$SAIDA"
    rm -f "$tmp"
}

caso "compra ok"            '{"flight":"IMD100","day":"2026-12-07","user":"cmp-ana"}'
caso "voo inexistente"      '{"flight":"XXX999","day":"2026-12-01","user":"cmp-ana"}'
caso "dia fora do catalogo" '{"flight":"IMD100","day":"1999-01-01","user":"cmp-ana"}'
caso "sem day"              '{"flight":"IMD100","user":"cmp-ana"}'
caso "user vazio"           '{"flight":"IMD100","day":"2026-12-07","user":""}'
caso "json malformado"      '{malformado'

# cabeçalho de correlação devolvido
cid="$(curl -s -o /dev/null -D - -H 'Content-Type: application/json' -H 'X-Correlation-Id: cmp-123' \
    -d '{"flight":"IMD100","day":"2026-12-07","user":"cmp-bia"}' "$BASE/buyTicket" \
    | grep -i '^x-correlation-id:' | cut -d' ' -f2 | tr -d '\r')"
echo "cid devolvido | $cid" >> "$SAIDA"

# /health e /sales: só os nomes dos campos
echo "health | $(curl -s "$BASE/health" | jq -c 'keys')" >> "$SAIDA"
echo "sales (campos) | $(curl -s "$BASE/sales" | jq -c '.[0] | keys')" >> "$SAIDA"

echo "Respostas gravadas em $SAIDA"
