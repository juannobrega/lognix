# Desenvolvimento

**Versão:** 0.1.0

## Estrutura

```
lognix/
├── pyproject.toml          # versão do produto (fonte de verdade)
├── docker-compose.yml      # instalação padrão
├── docker-compose.dev.yml  # hot reload e portas expostas
├── backend/                # FastAPI, SQLAlchemy async, Alembic
│   ├── lognix/             # pacote, organizado por domínio
│   ├── alembic/            # migrações
│   └── tests/              # pytest contra Postgres real
├── frontend/               # React + Vite + TypeScript, CSS Modules
├── alloy/                  # config inicial do Alloy
├── loki/                   # config do Loki
└── .github/workflows/      # ci.yml e release.yml
```

## Rodar com hot reload

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Backend em `http://localhost:8000` com reload, OpenAPI em `/api/docs`. Frontend:

```bash
cd frontend && npm install && npm run dev     # http://localhost:5173, proxy para :8000
```

## Backend sem Docker

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
docker run -d --name lognix-test-pg -e POSTGRES_USER=lognix -e POSTGRES_PASSWORD=lognix \
  -e POSTGRES_DB=lognix_test -p 5432:5432 postgres:16-alpine
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy lognix
```

Os testes aplicam as migrações do Alembic no banco `lognix_test` e esvaziam as tabelas entre casos.

## Frontend

```bash
cd frontend
npm run lint && npm run typecheck && npm test -- --run && npm run build
```

## Convenções

- Um domínio por pasta em `backend/lognix/`. Só `docker/`, `loki/`, `ai/` e `github/` falam com
  sistemas externos, cada um com o seu.
- Erros da API sempre em `{"error": {"code", "message", "action"}}`.
- Textos da interface em português.
- Branch de trabalho: `dev`. PR para `main` com label `release:*`.
