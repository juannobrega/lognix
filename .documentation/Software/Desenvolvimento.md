# Desenvolvimento

**Versão documentada:** 1.0.0

Como mexer no código. A visão de como o sistema funciona está em [Arquitetura](Arquitetura.md).

## Estrutura

```
lognix/
├── pyproject.toml          versão do produto, fonte de verdade para as tags
├── docker-compose.yml      a instalação, e a única que existe
├── backend/
│   ├── pyproject.toml      dependências e configuração de lint, tipos e testes
│   ├── lognix/             o pacote, organizado por domínio
│   ├── alembic/versions/   migrações, uma por fase
│   ├── scripts/measure.py  harness de medição de desempenho
│   └── tests/              pytest contra Postgres real
├── frontend/               React + Vite + TypeScript, CSS Modules
├── alloy/ loki/            configurações dos serviços
├── measure/                Prometheus e Grafana, fora da instalação padrão
└── .documentation/         Planning (decisões) e Software (este guia)
```

## O que cada módulo do backend faz

```
lognix/
├── auth/          usuários, login, sessões
├── hosts/         cadastro, validação em etapas, túneis SSH, proxy somente leitura
├── docker/        único módulo que fala com a Docker API, sempre pelo proxy
├── containers/    inventário, seleção de monitorados, projetos
├── events/        eventos Docker, reconciliação, redeploy
├── alloy/         gera e recarrega a config do Alloy
├── loki/          único módulo que fala com o Loki
├── analysis/      ciclo, padrões (Drain), classificação, triggers, executor
├── ai/            provedores, cadeia de fallback, contexto, esquema, insights, custo
├── notifications/ avisos com ação
├── settings/      configurações no banco, segredos criptografados
├── realtime/      WebSocket: logs ao vivo, executor, barramento
└── api/           agrega as rotas, saúde, resumo, sistema, métricas
```

Regra que o código segue: cada sistema externo tem **um** módulo que fala com ele. Nada fora de
`docker/` abre o socket do Docker; nada fora de `loki/` consulta o Loki; nada fora de `ai/` chama um
provedor de IA. Dentro de `ai/`, cada tipo de provedor é um arquivo em `ai/providers/`, e o resto do
módulo só conhece o `Protocol` `AiProvider`.

## Rodar

Há **um** compose, o de instalação. Para desenvolver, suba a infraestrutura por ele e rode backend e
frontend fora do Docker, onde o reload é imediato e o depurador funciona:

```bash
docker compose up -d postgres loki alloy
cd backend && .venv/bin/uvicorn lognix.main:app --reload
```

Backend em `localhost:8000`, OpenAPI em `/api/docs`. Frontend separado, com proxy para o backend:

```bash
cd frontend && npm install && npm run dev     # localhost:5173
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

Os testes aplicam as migrações no banco `lognix_test` e esvaziam as tabelas entre casos. Se uma
suíte travar, provavelmente sobrou uma conexão com transação aberta:

```bash
docker exec lognix-test-pg psql -U lognix -d postgres \
  -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='lognix_test'"
```

## Frontend

```bash
cd frontend
npm run lint && npm run typecheck && npm test -- --run && npm run build
```

## Como os testes evitam depender do mundo

Nada nos testes fala com SSH, Docker, Loki ou um provedor de IA de verdade. Em `backend/tests/`:

| Falso | Substitui | Usado por |
|---|---|---|
| `fake_docker.FakeDocker` | daemon Docker, num socket Unix local | túneis, inventário, eventos |
| `fake_ssh.FakeSshBackend` | conexão SSH; o "socket remoto" é o FakeDocker | hosts, validação, fingerprint |
| `conftest.ScriptedLoki` | Loki; devolve as linhas que o teste programar | ciclos de análise |
| `conftest.FakeAlloy` | endpoint de reload do Alloy | geração de config |
| `fake_ai.FakeAiProvider` | provedor de IA; responde o que o teste mandar | insights, retry, custos |
| `fake_ai.FakeRuntime` | a cadeia de provedores; grava os provedores falsos no banco | fallback, pausa por limite |

Isso deixa a suíte rápida e determinística. O que depende de verdade do mundo é verificado à mão
contra a stack real, e o resultado fica registrado no documento da fase.

## Migrações

```bash
cd backend
.venv/bin/alembic revision -m "descrição"      # esqueleto
.venv/bin/alembic upgrade head                 # aplicar
.venv/bin/alembic downgrade -1                 # voltar uma
```

Toda migração precisa de `downgrade` que funcione: a suíte de testes faz `downgrade base` antes de
subir o esquema. Tipos enum do Postgres precisam de `create(bind, checkfirst=True)` no upgrade e
`drop` no downgrade; veja as migrações existentes.

Registre o modelo novo em `alembic/env.py` e a tabela em `TABLES` no `conftest.py`, senão os testes
vazam dados entre casos.

## Medir desempenho

```bash
cd backend
.venv/bin/python scripts/measure.py --hosts 10 --containers 100 --lines 200 --rounds 3 \
  --api-seconds 30 --pause 30 --out medicao.json
```

Mede os critérios do ADR 009 contra Postgres real, com hosts e Loki simulados. Rode depois de mexer
no ciclo de análise.

## Convenções

- **Um módulo por sistema externo.** Só `docker/` fala com a Docker API, só `loki/` com o Loki,
  só `ai/` com o provider. Isso é verificado em revisão, não por ferramenta.
- **Erros da API** sempre em `{"error": {"code", "message", "action"}}`. O `action` é o que a
  pessoa deve fazer, e é obrigatório em erros de conexão.
- **Textos da interface e mensagens de erro em português.** Identificadores, labels e chaves de
  configuração em inglês.
- **Trabalho de CPU cede o loop.** Qualquer laço longo precisa de `await asyncio.sleep(0)` de tempos
  em tempos, ou a API trava junto.
- **Escrita no banco dentro de tarefa cancelável** precisa de `asyncio.shield`, e quem para a tarefa
  precisa esperar o trabalho blindado terminar. Sem isso sobram conexões com transação aberta.
- **Segredos** entram pela API e nunca saem: o `GET` devolve apenas se existe ou não.

## Branches e releases

Trabalho em `dev`. Pull request para `main` com exatamente uma label: `release:major`,
`release:minor`, `release:patch` ou `release:skip`. O workflow lê a label, escreve a versão no
`pyproject.toml` da raiz e no `package.json` do frontend, cria a tag e publica o release. Merge sem
label falha de propósito.
