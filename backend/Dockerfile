# Contexto de build: a RAIZ do repositório (precisa do pyproject.toml raiz para a versão).
#   docker build -f backend/Dockerfile .
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# openssh-client: túneis SSH (fase 0.2.0) caso a decisão seja subprocesso.
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client && rm -rf /var/lib/apt/lists/*
WORKDIR /app

FROM base AS deps
COPY backend/pyproject.toml ./
RUN pip install -e ".[dev]" 2>/dev/null || pip install .

FROM deps AS dev
COPY backend/ ./
COPY pyproject.toml /lognix-root-pyproject.toml
RUN python -c "import re,pathlib; t=pathlib.Path('/lognix-root-pyproject.toml').read_text(); v=re.search(r'(?m)^version = \"([^\"]+)\"', t).group(1); pathlib.Path('lognix/VERSION').write_text(v)"
RUN pip install -e ".[dev]"
EXPOSE 8000
CMD ["uvicorn", "lognix.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS runtime
COPY backend/ ./
COPY pyproject.toml /lognix-root-pyproject.toml
RUN python -c "import re,pathlib; t=pathlib.Path('/lognix-root-pyproject.toml').read_text(); v=re.search(r'(?m)^version = \"([^\"]+)\"', t).group(1); pathlib.Path('lognix/VERSION').write_text(v)" \
 && pip install . && rm /lognix-root-pyproject.toml
RUN useradd --create-home --uid 10001 lognix && mkdir -p /tunnels /alloy-config && chown -R lognix:lognix /tunnels /alloy-config /app
USER lognix
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn lognix.main:app --host 0.0.0.0 --port 8000"]
