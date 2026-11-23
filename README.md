# IMDTravel — Tolerância a Falhas (DIMAp/UFRN)

**Projeto Final · Parte 1 — Linha de base (tag `BASELINE`)**

Sistema didático de venda de passagens aéreas, construído para ser observado e derrubado de propósito.
Esta versão implementa o serviço **IMDTravel** (orquestrador) em **Python 3.14 + Flask** e **não possui nenhum
mecanismo de tolerância a falhas**: a ausência de proteção é o requisito, não descuido. A Parte 2 compara
o comportamento desta versão com a versão tolerante a falhas.

## Equipe

| Membro | Responsabilidades principais |
|---|---|
| **Elildes Fortaleza Santos** | Repositório e Git Flow, esqueleto Flask, log estruturado e correlação, clientes HTTP, registro de vendas, release |
| **Marcos Beraldo Barros** | `/health`, Dockerfile com uv, Docker Compose, `POST /buyTicket`, testes unitários, validação contra a referência, roteiro de observação, painel local, documentação |

## Arquitetura

Cada caixa é um container; todos sobem com um único comando e só o IMDTravel expõe porta ao hospedeiro.

```
                                   rede interna do Docker Compose (imdnet)
┌──────────┐  POST /buyTicket   ┌────────────────────────────────────────────────────────────┐
│ cliente  │ ─────────────────▶ │ IMDTravel (Python · Flask · Gunicorn)         porta 8080    │
│ curl/    │ ◀───────────────── │   GET /health · GET /sales · POST /buyTicket               │
│ testes.sh│   201 · 400 · 404  │   volume nomeado sales-data (/data/sales.db)               │
└──────────┘   409 · 500        └───────┬───────────────┬───────────────────┬────────────────┘
                                        │ 1 GET /flight │ 2 GET /convert    │ 4 POST /bonus
                                        │ 3 POST /sell  ▼                   ▼
                                        ▼          ┌──────────┐       ┌──────────┐
                                 ┌─────────────┐   │ Exchange │       │ Fidelity │
                                 │ AirlinesHub │   │ taxa     │       │ pontos   │
                                 │ estoque     │   └──────────┘       └──────────┘
                                 └─────────────┘
              AirlinesHub, Exchange e Fidelity: imagens publicadas no Docker Hub (caixas-pretas)
```

| Serviço | Origem | Papel |
|---|---|---|
| **IMDTravel** | Código deste repositório (`imdtravel/`) | Recebe a compra, orquestra as 4 chamadas e registra a venda |
| **AirlinesHub** | `gibeonufrn/imdtravel-airlineshub:baseline` | Estoque de assentos por (voo, dia) — único estado que importa |
| **Exchange** | `gibeonufrn/imdtravel-exchange:baseline` | Taxa de câmbio que caminha devagar (`rate`, `asOf`) |
| **Fidelity** | `gibeonufrn/imdtravel-fidelity:baseline` | Pontos de fidelidade por usuário |

## Fluxo de uma compra

As quatro chamadas são **síncronas** e a ordem é **obrigatória**:

```
cliente ─ POST /buyTicket {flight, day, user} ─▶ IMDTravel
   0. valida o pedido (400 se inválido, antes de chamar qualquer serviço)
   1. GET  /flight   ─▶ AirlinesHub   preço em dólar e assentos      (reversível)
   2. GET  /convert  ─▶ Exchange      taxa e asOf                      (reversível)
   3. POST /sell     ─▶ AirlinesHub   consome o assento (300–900 ms)   (IRREVERSÍVEL)
   4. POST /bonus    ─▶ Fidelity      credita pontos                   (no caminho crítico)
   5. grava a venda no registro local ─▶ 201 { transactionId, flight, day, user,
                                                valueUSD, valueBRL, rate, rateAsOf, bonus }
```

- `valueBRL = valueUSD × rate` (arredondado em 2 casas, com `Decimal`).
- Os números das dependências são lidos e devolvidos como `Decimal`: o preço `350.50` do AirlinesHub sai `350.50`, e não `350.5` (o `testes.sh` compara o texto).
- `bonus` = parte inteira de `valueUSD`.
- O `X-Correlation-Id` é gerado (ou aproveitado do cliente) e propagado nas quatro chamadas.

| Resultado | Quando |
|---|---|
| `201` | Compra concluída |
| `400 {"error":"invalid-request"}` | JSON malformado, campo ausente ou vazio |
| `404 {"error":"not-found"}` | Voo ou dia inexistente |
| `409 {"error":"sold-out"}` | Voo esgotado |
| `500` | Qualquer falha de dependência — sem tratamento, sem nova tentativa |

### O defeito de projeto (intencional)

O assento sai do estoque no passo 3. Se o passo 4 falhar (Fidelity fora do ar, por exemplo), a compra
devolve `500`, **o assento já foi consumido** e **nenhuma linha** é gravada em `/sales`. O bônus derruba
o que não deveria nem atrasar. Observar isso é um dos objetivos da Parte 1.

## Tecnologias

| Tecnologia | Uso | Por quê |
|---|---|---|
| **Python 3.14** | Linguagem | Escolha da equipe |
| **uv** | Dependências e ambiente virtual | `pyproject.toml` + `uv.lock`: a mesma instalação na máquina de cada um e no Docker |
| **Flask 3.1** | API REST | Leve e direto para três endpoints |
| **Gunicorn 27** (`gthread`, 1 worker, 256 threads, `--timeout 0`) | Servidor de produção | Atende muitas requisições simultâneas e **não** impõe timeout oculto (o padrão de 30 s do Gunicorn mataria requisições lentas e distorceria a observação). `--no-control-socket` desliga um recurso do Gunicorn 27 que não usamos |
| **requests** | Cliente HTTP | Sem `timeout=`, o padrão é esperar sem limite — exatamente o que a Parte 1 pede |
| **simplejson** | JSON com `Decimal` | Devolve os valores com o mesmo texto que vêm das dependências |
| **SQLite** (modo WAL) | Registro local de vendas | Arquivo em volume nomeado; sobrevive a `docker compose down` |
| **Docker + Docker Compose v2** | Infraestrutura | `docker compose up` basta; healthchecks e `depends_on: service_healthy` |
| **pytest + requests-mock** | Testes unitários | Simulam as dependências sem subir containers |
| **bash + curl + jq** (`testes.sh`) | Testes de sistema | Script fornecido pela disciplina |
| **rich** (`tools/painel.py`) | Painel local no terminal | Chamar os endpoints e ver a saúde dos containers |
| **Git Flow + GitHub** | Versionamento | `main`, `develop`, `feature/*`, `release/*`, `hotfix-*` |

### O que a Parte 1 proíbe (e como o código respeita)

| Proibido | Como é respeitado |
|---|---|
| Timeout nas chamadas | Nenhuma chamada passa `timeout=`; Gunicorn com `--timeout 0` |
| Retentativa | Nenhuma; um teste unitário confere que `/bonus` é chamado uma única vez |
| Fallback, cache, valor padrão, resposta degradada | Inexistentes; falha de dependência levanta `DependencyError` → 500 |
| Fila ou adiamento de chamadas | Quatro chamadas síncronas, em ordem |
| Limite de requisições simultâneas | Sem semáforo nem rate limit (256 threads) |
| `try/catch` que vire falha em sucesso | Os `except` só registram o log e relançam como erro |

### Instrumentação obrigatória

| Item | Implementação |
|---|---|
| **Correlação** | `X-Correlation-Id` gerado/aproveitado, propagado às 4 chamadas, devolvido no cabeçalho e gravado em `/sales` |
| **Log estruturado** | Um JSON por linha no `stdout`, com `ts`, `svc`, `cid`, `event`, `ms` (+ `method`, `path`, `status`, `dependency`, `url`). Eventos: `requisicao.recebida`, `chamada.saida`, `chamada.falhou`, `resposta.enviada`, `erro.inesperado` |
| **Sinal de vida** | `GET /health` → `200 {"status":"ok","uptimeS":N}`; verifica de verdade se o volume é gravável e se o SQLite responde (senão `503 {"status":"down","reason":...}`). Um `/health` com 200 não é logado |

## Dependências do sistema

| Ferramenta | Para quê | Conferir |
|---|---|---|
| Docker com **Compose v2** | Subir os quatro serviços | `docker compose version` |
| git | Clonar o repositório | `git --version` |
| bash, curl, jq | Rodar o `testes.sh` | `jq --version` |
| [uv](https://docs.astral.sh/uv/) (opcional) | Testes unitários e painel local, sem Docker | `uv --version` |

Reserve ao menos 4 GB de memória para o Docker. No **Windows**, use WSL 2 com Ubuntu e clone o repositório
dentro do sistema de arquivos do WSL (detalhes em [EXECUCAO.md](EXECUCAO.md)).

## Roteiro de execução

```bash
git clone https://github.com/Elildes/imdtravel.git
cd imdtravel
docker compose up -d --build --wait      # primeira vez: alguns minutos
docker compose ps                        # os quatro devem estar (healthy)
curl http://localhost:8080/health
```

Fazer uma compra e ver o registro:

```bash
curl -i -H 'Content-Type: application/json' -H 'X-Correlation-Id: demo-1' \
     -d '{"flight":"IMD100","day":"2026-12-01","user":"ana"}' \
     http://localhost:8080/buyTicket

curl http://localhost:8080/sales | jq
docker compose logs --no-log-prefix imdtravel | grep demo-1 | jq -c '{svc,event,ms,status}'
```

Parar:

| Comando | Efeito |
|---|---|
| `docker compose stop` / `start` | Para / retoma os containers |
| `docker compose down` | Remove containers e rede; **mantém** o registro de vendas |
| `docker compose down -v` | Remove também o volume: **apaga** o registro de vendas |

Painel local no terminal (compra, vendas, estoque, câmbio, pontos, logs por cid e a saúde dos 4 containers,
com monitoramento ao vivo):

```bash
uv run tools/painel.py
```

Sem compilar (imagens de referência do Docker Hub, inclusive o IMDTravel do professor):
`docker compose -f docker-compose.hub.yml up -d --wait`.

> O estoque de assentos, a taxa e os pontos vivem **em memória** nos três serviços de dependência:
> reiniciar um deles zera o seu estado. Só o registro de vendas do IMDTravel persiste (volume).

## Testes realizados

### 1. Testes unitários (pytest) — 25 testes, sem containers

```bash
cd imdtravel
uv sync              # cria o .venv com as dependências de desenvolvimento
uv run pytest -v     # 25 passed
```

| Área | O que é verificado |
|---|---|
| Compra feliz | 201, 9 campos, `valueBRL = 350,50 × 5,50 = 1927,75`, bônus 350, cid devolvido; preço devolvido como `350.50`; arredondamento em 2 casas |
| Ordem e correlação | `/flight → /convert → /sell → /bonus`, todas com o mesmo `X-Correlation-Id`; o Fidelity recebe `{user, bonus}` |
| Ausência de FT | Nenhuma chamada com `timeout`; `/bonus` chamado uma única vez (sem retry) |
| Registro | A compra aparece em `/sales` com cid, transactionId, par, usuário, valores e `ts`; cid gerado quando ausente |
| Entradas inválidas | 400 (sem `day`, `user` vazio ou só espaços, tipos errados, corpo não-objeto, JSON malformado) sem chamar nenhuma dependência |
| Erros de negócio | 404 (voo inexistente) e 409 (esgotado, sem bônus e sem linha em `/sales`) |
| Falhas de dependência | Fidelity 500 → 500, **`/sell` já chamado** e sem linha em `/sales`; Exchange fora do ar → 500 antes de vender; resposta que não é JSON → 500 |
| Observabilidade | Logs JSON com `ts/svc/cid/event/ms` e cid em toda linha; `/health` ok/down; `/health` 200 não polui o log |

### 2. Validação contra o IMDTravel de referência

O nosso IMDTravel e o de referência (`gibeonufrn/imdtravel-imdtravel:baseline`) receberam os mesmos pedidos
([`tests/capturar_respostas.sh`](tests/capturar_respostas.sh)). Status, campos e corpos de erro são iguais; a
única diferença é o corpo do 400 para JSON malformado (a referência devolve o erro padrão do Spring).
Detalhes em [`tests/referencia/COMPARACAO.md`](tests/referencia/COMPARACAO.md).

### 3. Teste de sistema — `testes.sh` (fornecido pela disciplina)

```bash
./testes.sh                  # ~10 s, contra o sistema no ar
./testes.sh --com-falhas     # inclui o Fidelity parado (pode levar minutos)
./testes.sh --reiniciar      # apaga o volume e sobe do zero antes de testar
```

Cobre `/health` dos 4 serviços, compra completa (9 campos, estoque −1, `/sales`, bônus e cid no Fidelity),
cid gerado, determinismo de preço e taxa, pedidos inválidos, esgotamento sob concorrência (20×201 e 5×409)
e, com `--com-falhas`, o caso do Fidelity parado. Guia completo em [TESTES.md](TESTES.md).

Resultado com `--com-falhas`: **43 passaram, 0 falharam** no nosso IMDTravel e no de referência
([`tests/evidencias/`](tests/evidencias/)). Com o Fidelity parado, o nosso devolve 500 em ~1 s e o de
referência em ~40 s: nenhum dos dois tem timeout; o `requests` desiste na hora quando o nome `fidelity`
some do DNS interno do Docker.

### 4. Roteiro de observação de falhas

Com o sistema no ar, [`tests/roteiro_observacao.sh`](tests/roteiro_observacao.sh) provoca as falhas (parando
ou congelando containers) e grava a evidência de cada cenário (estoque e `/sales` antes e depois, status,
tempo e o log JSON da compra) em [`tests/evidencias/`](tests/evidencias/). Leva ~3 minutos.

| Cenário | Como provocar | O que observar |
|---|---|---|
| Fidelity parado | `docker compose stop fidelity` | 500, **assento consumido**, nenhuma linha em `/sales`, tempo até o erro |
| Fidelity "pendurado" | `docker compose pause fidelity` | A compra fica presa: não há timeout; medir a duração |
| Exchange parado | `docker compose stop exchange` | 500 antes de vender; estoque intacto |
| AirlinesHub parado | `docker compose stop airlineshub` | 500 já na consulta do voo |
| Conferência | Comparar `GET /sales` com o estoque do AirlinesHub | Divergência = venda sem registro |
| Idade da taxa | Duas compras com 15 s de intervalo | `rate` e `rateAsOf` mudam a cada ~10 s |

Observado: com o Fidelity parado, 500 em menos de 1 s e **um assento perdido** (estoque 20 → 19, `/sales`
inalterado); com o Fidelity congelado, a compra fica presa até ele voltar e então é gravada, mesmo com o
cliente já tendo desistido; Exchange e AirlinesHub parados devolvem 500 sem consumir assento; na conferência,
o AirlinesHub vendeu 4 assentos e o `/sales` registrou 3.

```bash
docker compose exec airlineshub curl -s "localhost:8080/flight?flight=IMD100&day=2026-12-01"
```

## Catálogo de voos

3 voos × 7 dias consecutivos, **20 assentos** em cada par (voo, dia), recriado a cada subida do container.
O preço é determinístico: preço-base + US$ 12,25 por dia a partir de `2026-12-01`.

| Voo | 12-01 | 12-02 | 12-03 | 12-04 | 12-05 | 12-06 | 12-07 |
|---|---|---|---|---|---|---|---|
| **IMD100** | 350,50 | 362,75 | 375,00 | 387,25 | 399,50 | 411,75 | 424,00 |
| **IMD200** | 420,50 | 432,75 | 445,00 | 457,25 | 469,50 | 481,75 | 494,00 |
| **IMD300** | 510,50 | 522,75 | 535,00 | 547,25 | 559,50 | 571,75 | 584,00 |

Valores em dólar. Exchange: taxa inicial 5,50, variação de até ±0,3 % a cada 10 s, faixa 5,00–6,00.

### Configuração (variáveis de ambiente)

| Variável | Padrão | Serviço |
|---|---|---|
| `CATALOG_FLIGHTS` | `IMD100,IMD200,IMD300` | AirlinesHub |
| `CATALOG_BASE_PRICES` | `350.50,420.50,510.50` | AirlinesHub |
| `CATALOG_PRICE_STEP_PER_DAY` | `12.25` | AirlinesHub |
| `CATALOG_START_DATE` / `CATALOG_DAYS` / `CATALOG_SEATS` | `2026-12-01` / `7` / `20` | AirlinesHub |
| `SELL_MIN_MS` / `SELL_MAX_MS` | `300` / `900` | AirlinesHub |
| `EXCHANGE_INITIAL_RATE` | `5.50` | Exchange |
| `EXCHANGE_TICK_S` / `EXCHANGE_MAX_STEP_PCT` | `10` / `0.3` | Exchange |
| `EXCHANGE_MIN` / `EXCHANGE_MAX` | `5.00` / `6.00` | Exchange |
| `AIRLINESHUB_URL` / `EXCHANGE_URL` / `FIDELITY_URL` | `http://<serviço>:8080` | IMDTravel |
| `SALES_DIR` / `PORT` | `/data` / `8080` | IMDTravel |
| `IMDTRAVEL_HOST_PORT` | `8080` | Porta no seu computador |

## Estrutura do repositório

```
.
├── docker-compose.yml          # 3 imagens do Hub + build do IMDTravel
├── docker-compose.hub.yml      # sistema inteiro com imagens publicadas (referência)
├── testes.sh                   # verificação funcional (fornecida)
├── README.md · EXECUCAO.md · TESTES.md
├── docs/                       # especificação e figuras
├── tests/                      # evidências, comparação com a referência e scripts de observação
├── tools/painel.py             # painel local em rich (uv run tools/painel.py)
└── imdtravel/
    ├── Dockerfile · pyproject.toml · uv.lock · wsgi.py
    ├── app/
    │   ├── __init__.py         # create_app
    │   ├── json_decimal.py     # JSON com Decimal (simplejson)
    │   ├── config.py           # variáveis de ambiente
    │   ├── errors.py           # exceções de domínio → HTTP
    │   ├── logging_json.py     # log estruturado
    │   ├── correlation.py      # X-Correlation-Id
    │   ├── clients.py          # as 4 chamadas (sem timeout/retry)
    │   ├── purchase.py         # orquestração
    │   ├── storage.py          # registro de vendas (SQLite)
    │   └── routes.py           # /buyTicket · /sales · /health
    └── unit/                   # testes unitários
```

## Fluxo de trabalho (Git Flow)

| Ramo | Origem | Uso |
|---|---|---|
| `main` | — | Entregas (recebe/produção `release` e `hotfix`) |
| `develop` | `main` | Integração (ramo padrão no GitHub) |
| `feature/<n>-<nome>` | `develop` | Uma por issue; PR para `develop` com `Closes #n` |
| `release/<versão>` | `develop` | Fechamento e **tag** (`BASELINE`); depois `main` e `develop` |
| `hotfix-<n>` | `main` | Bug crítico; depois `main`, `develop` e `release` |

Commits seguem `tipo: descrição (#issue)` (`feat`, `fix`, `docs`, `test`, `chore`). A tag `BASELINE`
**nunca é movida**: a Parte 2 depende dela para comparar as duas versões.

## Problemas comuns

| Sintoma | Solução |
|---|---|
| `port is already allocated` na 8080 | `IMDTRAVEL_HOST_PORT=9090 docker compose up -d --wait` |
| Serviço preso em `(health: starting)` | Aumente a memória do Docker; `docker compose logs <serviço>` |
| `bad interpreter` / `$'\r'` no Windows | `sed -i 's/\r$//' testes.sh` (o `.gitattributes` já força LF) |
| `testes.sh`: nenhum par com assento livre | `./testes.sh --reiniciar` |
| Uma compra demora minutos para dar erro | **Esperado na Parte 1**: não há timeout nas chamadas de saída |
