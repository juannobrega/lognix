# Stack Tecnológica

**Status:** Aprovado em 2026-11-21 · **Atualizado:** 2026-11-21

Tecnologias decididas. Versões exatas são fixadas no início da construção e registradas na
documentação do software, não aqui.

## Backend

| Item | Escolha | Motivo |
|---|---|---|
| Linguagem | Python 3.12+ | Decisão de produto |
| Framework web | FastAPI | Async nativo, tipagem com Pydantic, OpenAPI gerado, WebSocket e SSE |
| ORM e migrações | SQLAlchemy 2 async + Alembic | Padrão do ecossistema, async compatível com FastAPI |
| Banco de metadados | PostgreSQL | Concorrência real, JSONB para insights, maturidade. Guarda só o que o Lognix produz, nunca linhas de log |
| Agendamento e tarefas | Um loop async por container monitorado, mais APScheduler para tarefas periódicas como inventário | Sem Redis na primeira fase, condicionado a medição. Ver ADR 009 |
| Túnel SSH | A decidir em protótipo: `asyncssh` ou binário `ssh` como subprocesso | Decisão de implementação, não bloqueia planejamento |
| Cliente Docker | `aiodocker` ou chamadas HTTP diretas via `httpx` sobre socket Unix | Passa sempre pelo proxy somente leitura |
| Cliente Loki | `httpx` contra a API HTTP do Loki | API simples, não compensa biblioteca |
| Agrupamento de padrões | Drain, via biblioteca existente como `drain3` | Algoritmo consolidado, sem IA nessa etapa |
| Autenticação | JWT com `PyJWT`, senhas com `argon2` | Ver ADR 008 |
| Cliente de IA | SDK OpenAI apontando para o OpenRouter, atrás da interface `AIProvider` | Ver ADR 006 |
| Cliente GitHub | `PyGithub` ou `httpx` direto, autenticação por GitHub App | Ver ADR 007. Fase posterior |
| Testes | `pytest`, `pytest-asyncio`, `httpx` para testes de API | |
| Qualidade | `ruff` para lint e formatação, `mypy` para tipos | |

## Frontend

| Item | Escolha | Motivo |
|---|---|---|
| Biblioteca | React 18+ | Decisão de produto |
| Build | Vite | Decisão de produto |
| Linguagem | TypeScript | Contratos tipados com a API, menos erro em telas de dados densos |
| Estilo | CSS Modules | Continua CSS puro, escopo por componente, sem framework de utilitários |
| Componentes acessíveis | Radix UI primitives | Diálogo, select, tooltip, abas, switch: comportamento e acessibilidade prontos, estilo nosso. Ver ADR 011 |
| Fonte | Geist Sans e Mono via `@fontsource-variable` | Servida pelo próprio pacote: a CSP do nginx bloqueia CDNs |
| Roteamento | React Router | Padrão |
| Dados remotos | TanStack Query | Cache, revalidação e estado de carregamento para dados que mudam a cada ciclo |
| Tempo real | WebSocket ou SSE do backend para eventos; tail do Loki para logs ao vivo | Detalhar em 06 Frontend |
| Testes | Vitest, Testing Library | |
| Qualidade | ESLint, Prettier | |

## Coleta e armazenamento

| Item | Escolha | Motivo |
|---|---|---|
| Coletor | Grafana Alloy | Decisão de produto. Roda ao lado do Lognix. Ver ADR 002 |
| Armazenamento de logs | Grafana Loki, modo monolítico, filesystem | Ver ADR 001 |
| Retenção padrão | 15 dias, configurável no `.env` | Equilíbrio entre investigação e disco em instalação pequena |

## Infraestrutura

| Item | Escolha | Motivo |
|---|---|---|
| Orquestração local | Docker Compose | Instalação por `docker compose up` |
| Containers na primeira fase | backend, frontend, postgres, loki, alloy | Cinco. Redis só se a medição exigir |
| Volumes | `postgres-data`, `loki-data`, `tunnels` compartilhado entre backend e Alloy | |
| Imagens | Publicadas em registro público quando houver release | Roadmap |

## Fora da stack, por decisão

- Redis, Celery, arq: só se ADR 009 for substituído.
- Tailwind ou qualquer framework CSS utilitário.
- Grafana como interface. O Lognix tem interface própria. Grafana pode ser adicionado por quem quiser, apontando para o mesmo Loki.
