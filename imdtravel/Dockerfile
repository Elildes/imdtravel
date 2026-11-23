FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    SALES_DIR=/data

# curl é exigido pelo healthcheck do Compose (a imagem slim não o traz)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# uv: instala as dependências exatamente como estão no uv.lock
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv

WORKDIR /srv
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/srv/.venv/bin:$PATH"

# dependências antes do código: aproveita o cache de camadas do Docker
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-cache

COPY app ./app
COPY wsgi.py .

# usuário sem privilégios; /data pertence a ele (o volume nomeado herda esta permissão)
RUN useradd --system --uid 10001 imd && mkdir -p /data && chown imd /data
USER imd

EXPOSE 8080

# --timeout 0 : o Gunicorn NÃO pode matar requisições lentas (seria um timeout escondido)
# --threads   : muitas threads, para não limitar as requisições simultâneas na entrada
# --no-control-socket : desliga o socket de administração do Gunicorn 27 (não é usado)
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --worker-class gthread --workers 1 --threads 256 --timeout 0 --no-control-socket wsgi:app"]
