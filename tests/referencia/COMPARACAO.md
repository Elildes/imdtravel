# Comparação com o IMDTravel de referência (#11)

Executado em 23/11/2026. Referência: imagem `gibeonufrn/imdtravel-imdtravel:baseline`, num projeto
compose separado na porta 9090 (`COMPOSE_PROJECT_NAME=imdtravel-ref IMDTRAVEL_HOST_PORT=9090`).
Nosso: `docker-compose.yml` deste repositório, na porta 8080.

## Formato das respostas (`tests/capturar_respostas.sh`)

Arquivos: [`respostas-referencia.txt`](respostas-referencia.txt) e [`respostas-nosso.txt`](respostas-nosso.txt).

| Caso | Referência | Nosso | |
|---|---|---|---|
| Compra ok | 201, 9 campos | 201, os mesmos 9 campos | igual |
| Voo inexistente / dia fora do catálogo | 404 `{"error":"not-found"}` | idem | igual |
| Sem `day` / `user` vazio | 400 `{"error":"invalid-request"}` | idem | igual |
| JSON malformado | 400, corpo padrão do Spring (`timestamp`, `status`, `error`, `path`) | 400 `{"error":"invalid-request"}` | **status igual, corpo diferente** |
| `X-Correlation-Id` enviado | devolvido igual | devolvido igual | igual |
| `/health` | `status`, `uptimeS` | idem | igual |
| `/sales` | 8 campos | os mesmos 8 campos | igual |

A única diferença é o corpo do 400 para JSON malformado. Mantivemos o nosso: o `testes.sh` confere só o
status, e o nosso corpo é o mesmo dos outros pedidos inválidos.

## `testes.sh --com-falhas`

| | Referência | Nosso |
|---|---|---|
| Resultado | 43 passaram, 0 falharam | 43 passaram, 0 falharam |
| Seção 6: 25 compras simultâneas, 20 assentos | 20 × 201, 5 × 409 | 20 × 201, 5 × 409 |
| Seção 7: Fidelity parado | 500 em **40 s** | 500 em **1 s** |

Saídas completas: [`../evidencias/testes-sh-referencia.log`](../evidencias/testes-sh-referencia.log) e
[`../evidencias/testes-sh-nosso.log`](../evidencias/testes-sh-nosso.log).

**Por que o nosso falha mais rápido com o Fidelity parado:** nenhum dos dois tem timeout. Quando o container
para, o nome `fidelity` deixa de existir no DNS interno do Docker. O `requests` (Python) recebe a falha de
resolução e desiste na hora: o log mostra `chamada.falhou` com `error: ConnectionError` em ~15 ms. A
referência (Java) leva cerca de 40 s para desistir. A diferença vem da biblioteca HTTP de cada um, não de
uma proteção.

## Log estruturado

O nosso IMDTravel escreve uma linha JSON por evento (`ts`, `svc`, `cid`, `event`, `ms`), com o cid em todas.
A imagem de referência do IMDTravel não escreve linhas JSON no stdout: só o log de texto do Spring.
