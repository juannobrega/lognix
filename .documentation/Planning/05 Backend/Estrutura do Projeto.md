# Estrutura do Projeto

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Layout do monorepo e organização interna do backend.

## 1. Monorepo

```
lognix/
├── pyproject.toml            # mínimo: nome, versão (fonte de verdade), sem código
├── docker-compose.yml        # instalação padrão
├── .env.example
├── README.md
├── LICENSE
├── .github/workflows/        # release.yml, ci.yml, docs.yml
├── .documentation/           # Planning/ e Software/
├── backend/
│   ├── pyproject.toml        # dependências e config do backend; versão lida da raiz no build
│   ├── alembic/              # migrações
│   ├── lognix/               # pacote Python
│   └── tests/
├── frontend/
│   ├── package.json          # version atualizada pelo workflow
│   ├── vite.config.ts
│   ├── src/
│   └── nginx.conf            # serve estáticos e faz proxy de /api e /ws para o backend
├── alloy/
│   └── config.alloy          # placeholder; o backend sobrescreve no volume
└── loki/
    └── loki-config.yaml      # monolítico, filesystem, retenção do .env
```

Versão: o build do backend copia a versão do `pyproject.toml` raiz para o pacote, e o frontend a lê do
`package.json`. Ambos vêm do mesmo passo do workflow de release. A versão aparece em `GET /api/health`
e no rodapé da interface.

## 2. Pacote `lognix/`

Organização por **domínio**, não por camada técnica. Cada domínio tem seus modelos, esquemas, serviço
e rotas juntos.

```
lognix/
├── main.py                  # cria app FastAPI, monta rotas, inicia loops
├── config.py                # leitura do .env, tipada
├── db.py                    # engine async, sessão, base
├── security/                # criptografia em repouso, hash de senha, JWT
├── auth/                    # User, login, cadastro
├── hosts/                   # Host, TunnelState, validação em etapas, supervisor de túneis
│   ├── tunnel/              # abertura SSH, encaminhamento de socket, reconexão
│   └── readonly_proxy/      # proxy GET-only sobre socket Unix, lista de caminhos permitidos
├── docker/                  # cliente Docker API via proxy: inventário, inspeção, eventos
├── containers/              # Container, seleção de monitorados, excluídos, redeploy
├── alloy/                   # gerador de config, recarga, AlloyConfigVersion
├── loki/                    # cliente LogQL, tail, labels
├── analysis/                # ciclo por container, janela, Drain, classificador, AnalysisRun
│   ├── patterns/            # Drain e Pattern
│   ├── classifier/          # nível estruturado e regex versionadas
│   └── triggers/            # erro, evento, anomalia, manual; TriggerFired
├── ai/                      # AIProvider, OpenRouter, pipeline de contexto, esquema, retry, AICall
│   └── prompts/             # arquivos versionados
├── insights/                # Insight, visto, limpar todos, histórico
├── notifications/           # Notification
├── settings/                # Setting criptografado, tela de configuração
├── github/                  # fase 1.1+: App, RepositoryLink, código, issues
├── realtime/                # WebSocket: executor, notificações, tail de logs
└── api/                     # agrega routers por domínio sob /api/v1
```

Regras:

- Um domínio não importa modelos de outro diretamente; usa o serviço do outro domínio.
- `docker/` é o **único** módulo que fala com a Docker API, e sempre pelo proxy. Teste garante que
  nenhum outro módulo abre socket em `/tunnels`.
- `loki/` é o único que fala com o Loki.
- `ai/` é o único que fala com o OpenRouter.
- `github/` é o único que fala com o GitHub.

## 3. Processos em execução

Tudo em um único processo FastAPI, ADR 009:

| Loop | Um por | Intervalo |
|---|---|---|
| Ciclo de análise | container monitorado | 30 s após o fim do anterior |
| Supervisor de túnel | host | verificação a cada 15 s |
| Ouvinte de eventos | host | stream contínuo |
| Reconciliação de inventário | host | 60 s |
| Tarefas periódicas | global | APScheduler: limpeza de retenção, cache de preços de modelos |

Loops são iniciados no `startup` do FastAPI e encerrados no `shutdown`, com cancelamento limpo.
Estado dos loops é exposto em `GET /api/health/loops` para diagnóstico.

## 4. Configuração via `.env`

Só o que precisa existir **antes** do primeiro login. Tudo o mais é configurado pela interface.

| Variável | Uso |
|---|---|
| `LOGNIX_SECRET_KEY` | criptografia em repouso e assinatura de JWT. Perder = perder credenciais |
| `DATABASE_URL` | Postgres |
| `LOKI_URL`, `LOKI_RETENTION_DAYS` | Loki e retenção |
| `ALLOY_URL`, `ALLOY_CONFIG_PATH` | recarga e caminho da config |
| `TUNNELS_DIR` | volume dos sockets |
| `LOGNIX_PUBLIC_URL` | usado em links de issues, fase GitHub |

## 5. Testes

| Tipo | Escopo | Ferramenta |
|---|---|---|
| Unitário | classificador, Drain, redução de contexto, validação de esquema, gerador de config | pytest |
| Integração | API com Postgres real em container, proxy somente leitura contra Docker local | pytest + testcontainers |
| Contrato | esquema JSON da IA contra respostas gravadas | pytest |
| Proxy | tenta `POST`, `DELETE` e caminhos fora da lista; todos devem falhar | pytest, obrigatório no CI |
| Ponta a ponta | host de teste em container com `sshd` e Docker-in-Docker: cadastro, túnel, coleta, log na interface | fase 0.3.0 em diante |
