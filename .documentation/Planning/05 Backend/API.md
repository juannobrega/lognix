# API

**Status:** Aprovado em 2026-11-21 · **Atualizado:** 2026-11-26

REST sob `/api/v1`, JSON, autenticado por JWT exceto onde indicado. WebSocket sob `/ws`.

> **A lista de endpoints deste documento é a da 0.4.0 e não é mantida.** A referência da API é a
> OpenAPI que a própria instalação serve em `/api/docs`, gerada do código e portanto sempre certa.
> O que vale aqui são as **convenções** da seção 1: elas são contrato, valem para rota que ainda
> nem existe, e é por isso que o documento continua de pé.
>
> Manter uma cópia da lista em markdown foi tentado e não funcionou: a 1.0.0 tem 56 rotas, a lista
> abaixo tem as de quatro fases atrás, e ninguém percebeu até esta revisão. Lista copiada à mão é
> lista que envelhece calada — e uma errada é pior que nenhuma, porque parece confiável.

## 1. Convenções

- Identificadores são uuid do Lognix. IDs do Docker nunca aparecem como chave de rota.
- Listas paginadas por cursor: `?limit=50&cursor=...`, resposta com `items` e `next_cursor`.
- Erros em formato único: `{ "error": { "code": "host_unreachable", "message": "...", "action": "..." } }`.
  `action` é a sugestão legível, obrigatória em erros de conexão.
- Datas em ISO 8601 UTC.
- Versionamento na rota. Quebra de contrato é `release:major` após 1.0.0.

## 2. Endpoints

### Saúde e sistema, sem autenticação onde marcado
| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | versão, estado de Postgres, Loki, Alloy. **Público** |
| GET | `/health/loops` | estado de cada loop: ciclos, túneis, eventos. Autenticado |
| GET | `/setup/status` | `needs_setup: true` se não há usuários. **Público** |
| POST | `/setup` | cria o primeiro usuário. Só funciona com banco vazio. **Público** |

### Autenticação
| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/login` | email e senha → `access_token`, `refresh_token`. **Público** |
| POST | `/auth/refresh` | novo access token |
| POST | `/auth/logout` | invalida refresh |
| GET | `/auth/me` | usuário atual |

### Usuários
| Método | Rota | Descrição |
|---|---|---|
| GET | `/users` | lista |
| POST | `/users` | cria |
| DELETE | `/users/{id}` | remove. Não pode remover o último |
| PUT | `/users/me/password` | troca a própria senha |

### Hosts
| Método | Rota | Descrição |
|---|---|---|
| GET | `/hosts` | lista com estado |
| POST | `/hosts` | cria e inicia validação. Devolve `202` com `validation_id` |
| GET | `/hosts/validations/{id}` | progresso das seis etapas, para a tela de cadastro. Também por WebSocket |
| GET | `/hosts/{id}` | detalhe, estado do túnel, fingerprint |
| PUT | `/hosts/{id}` | edita nome e credenciais; dispara revalidação |
| POST | `/hosts/{id}/reconnect` | força reconexão |
| POST | `/hosts/{id}/accept-fingerprint` | aceita novo fingerprint |
| DELETE | `/hosts/{id}` | remove: oculta, encerra túnel, mantém dados |
| DELETE | `/hosts/{id}?purge=true` | apaga de fato, inclusive logs no Loki. Exige confirmação com o nome do host no corpo |
| GET | `/hosts/{id}/containers` | inventário com `monitored` |
| PUT | `/hosts/{id}/containers/monitored` | lista de ids monitorados. Recarrega Alloy |
| GET | `/hosts/{id}/events` | HostEvent |
| GET | `/hosts/{id}/alloy-config` | config atual e versões |

### Projetos (containers)
| Método | Rota | Descrição |
|---|---|---|
| GET | `/projects` | monitorados de todos os hosts |
| GET | `/projects/{id}` | detalhe, estado, tipo, repositório |
| GET | `/projects/{id}/logs` | histórico: `start`, `end`, `q` texto, `level`, `stream`, `limit`, `direction` |
| GET | `/projects/{id}/patterns` | padrões com contagem |
| GET | `/projects/{id}/events` | DockerEvent |
| GET | `/projects/{id}/insights` | insights do projeto |
| GET | `/projects/{id}/analysis-runs` | ciclos recentes |
| POST | `/projects/{id}/analyze` | trigger manual: `start`, `end`. `429` se dentro de 1 min do último |
| GET | `/projects/excluded` | containers excluídos |

### Insights
| Método | Rota | Descrição |
|---|---|---|
| GET | `/insights` | novos. Filtros: host, projeto, severidade, trigger |
| GET | `/insights/history` | vistos |
| GET | `/insights/unanalyzed` | TriggerFired sem insight |
| GET | `/insights/{id}` | detalhe com evidências resolvidas, contexto enviado, chamada de IA |
| POST | `/insights/{id}/seen` | marca visto |
| POST | `/insights/seen-all` | limpar todos, com os mesmos filtros da lista |

### Notificações
| Método | Rota | Descrição |
|---|---|---|
| GET | `/notifications` | novas |
| POST | `/notifications/{id}/seen` | visto |
| POST | `/notifications/seen-all` | limpar todos |

### Configurações
| Método | Rota | Descrição |
|---|---|---|
| GET | `/settings` | todas, valores sensíveis mascarados |
| PUT | `/settings/ai` | chave, modelo, limites, ativo |
| POST | `/settings/ai/test` | chamada mínima, devolve modelo, latência, custo |
| GET | `/settings/ai/models` | lista do OpenRouter com preços, cacheada |
| GET | `/settings/usage` | consumo agregado: período, host, projeto, trigger, propósito |
| GET | `/settings/usage/calls` | chamadas individuais, paginadas |
| GET | `/settings/system` | versão, retenção, estado de componentes |

### GitHub, fase 1.1+
`/settings/github`, `/projects/{id}/repository`, `/insights/{id}/issue`. Detalhado na área 09.

## 3. WebSocket `/ws`

Autenticação por token na query na abertura; sem token válido o handshake é recusado com HTTP 403. Canais por mensagem `subscribe`:

| Canal | Payload | Uso |
|---|---|---|
| `logs:{project_id}` | linhas conforme chegam do tail do Loki. **Implementado na 0.4.0** | logs ao vivo |
| `executor` | início, mudança de fase e fim de cada análise | painel do executor |
| `notifications` | nova notificação, contadores | barra lateral |
| `insights` | novo insight, contador | barra lateral e painel |
| `hosts` | mudança de estado de host | lista de hosts |
| `validation:{id}` | progresso das etapas de validação | cadastro de host |

Um cliente mantém uma única conexão com várias inscrições.

## 4. Limites

- Logs: máximo 5 000 linhas por requisição. Acima, paginar por cursor temporal.
- Tail: o backend mantém um tail por projeto ativo, compartilhado entre clientes.
- Rate limit só em `/auth/login`, 10 por minuto por IP, e em `/projects/{id}/analyze`.
