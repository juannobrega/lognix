# Monitoramento Docker

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

O que o backend lê da Docker API de cada host, além dos logs que o Alloy coleta. Base: ADR 003 e 004.

## 1. Inventário

Sincronização do inventário de containers de um host:

| Quando | Como |
|---|---|
| Na conexão | `GET /containers/json?all=1` |
| A cada 60 s | mesma chamada, reconcilia com o banco |
| Em evento `start`, `die`, `destroy` | atualização imediata do container afetado |

Reconciliação:

| Situação | Ação |
|---|---|
| Container no Docker e não no banco | cria `Container` com `monitored = false`, notificação `new_container` |
| Container no banco e não no Docker | `state = removed`, `monitored = false`, vai para aba Containers excluídos, recarrega Alloy se era monitorado |
| Container nos dois | atualiza `state`, `name`, `image`, `image_digest`, `labels` |

Identidade: o Lognix casa primeiro pelo `docker_id`. Se não encontra, tenta a **identidade de
serviço** descrita na seção 6, antes de concluir que é um container novo.

## 2. Mapeamento Docker → Container

| Campo Docker | Campo Lognix |
|---|---|
| `Id` | `docker_id` |
| `Names[0]` sem `/` | `name` |
| `Image` | `image` |
| `ImageID` ou digest via inspect | `image_digest` |
| `State` | `state` |
| `Labels` | `labels` jsonb |
| `Labels["com.docker.compose.project"]` | `compose_project` |
| `Labels["com.docker.compose.service"]` | `compose_service` |
| `Labels["org.opencontainers.image.source"]` | pré-preenche `RepositoryLink.owner/repo` |
| `Labels["org.opencontainers.image.revision"]` | pré-preenche `RepositoryLink.default_ref` |

Labels OCI vêm da imagem e aparecem no container quando o Dockerfile as define. Quando não existem,
o usuário vincula manualmente.

## 3. Eventos

Um stream `GET /events` por host, aberto pelo backend logo após o túnel. Filtro: `type=container`.

| Evento Docker | Ação no Lognix | Alimenta trigger |
|---|---|---|
| `start` | inventário, notificação se desconhecido | não |
| `die` com `exitCode != 0` | grava `DockerEvent`, | **sim**, evento crítico |
| `die` com `exitCode = 0` | grava | não |
| `oom` | grava | **sim**, evento crítico |
| `restart` | grava, conta restarts em 5 min | **sim** se ≥ 3 em 5 min, restart em loop. Confirmado |
| `redeploy` (sintético, gerado pelo Lognix) | grava com imagem anterior e nova | não dispara, mas entra no contexto de qualquer trigger seguinte |
| `kill`, `stop`, `pause`, `unpause` | grava | não |
| `health_status: unhealthy` | grava | **sim**, evento crítico |
| `destroy` | inventário, container excluído | não |

Eventos só são gravados para containers **monitorados**. Para os demais, só `start` e `destroy` são
usados para inventário e descartados em seguida.

Se o stream de eventos cair, o backend reabre com `since` igual ao último evento recebido, para não
perder eventos durante a reconexão.

## 4. Inspeção

`GET /containers/{id}/json` é chamado:

- quando o container é marcado como monitorado, para preencher `image_digest`, labels OCI e variáveis
  de ambiente úteis ao diagnóstico, como nome do serviço e versão;
- quando um trigger dispara, para anexar ao contexto da IA o estado atual, restarts e healthcheck.

Variáveis de ambiente são armazenadas **apenas por nome**, nunca por valor, exceto uma lista explícita
de nomes seguros como `APP_VERSION`, `GIT_COMMIT`, `NODE_ENV`. Valores podem conter segredos.

## 5. Coleta começa na marcação

Regra de produto, confirmada em 2026-11-21: ao marcar um container, logs anteriores **não** são
coletados. Motivos: evitar despejo de histórico no Loki e evitar que erros antigos disparem dezenas
de triggers e chamadas de IA no primeiro ciclo. Detalhe de implementação em [Grafana Alloy](Grafana%20Alloy.md), seção 6.

Consequência para a interface: logo após marcar, a tela de logs fica vazia até a primeira linha nova
chegar. A interface precisa dizer isso, em vez de parecer quebrada.

## 6. Containers recriados por deploy

Decisão de 2026-11-21. `docker compose up` após um build recria o container com novo `docker_id`.
Sem tratamento, isso geraria um container excluído mais um novo não monitorado a cada deploy.

**Reconhecimento por identidade de serviço.** Se um container novo aparece
com o mesmo `compose_project` e `compose_service` de um container monitorado que acabou de ir para
excluídos no mesmo host, o Lognix trata como **o mesmo projeto**: mantém o `Container.id`, atualiza
`docker_id`, `image` e `image_digest`, continua monitorando, recarrega o Alloy, e registra um
`DockerEvent` do tipo `redeploy`. Sem labels de Compose, usa o nome do container como identidade.

Isso também dá à IA o dado mais valioso para diagnóstico: "o erro começou logo após o redeploy da
imagem X para a imagem Y".

## 7. Limites

- Sem métricas de CPU e memória. Roadmap.
- Sem leitura de `docker compose` do host. O Lognix só vê o que o daemon expõe.
- Sem suporte a Docker Swarm. Roadmap.
