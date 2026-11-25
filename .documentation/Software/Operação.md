# Operação

**Versão:** 0.9.0

## Preparar um host para o Lognix

O Lognix não instala nada no host. Ele precisa só de SSH e de acesso ao socket do Docker.

1. **Usuário SSH.** Crie um usuário dedicado e coloque-o no grupo `docker`:
   ```bash
   sudo useradd -m -s /bin/bash lognix
   sudo usermod -aG docker lognix
   ```
2. **Autenticação.** Prefira chave. Gere no seu computador e instale a pública no host:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/lognix -N ''
   ssh-copy-id -i ~/.ssh/lognix.pub lognix@HOST
   ```
   Cole o conteúdo de `~/.ssh/lognix` no cadastro. Senha e chave com passphrase também funcionam.
3. **Encaminhamento no sshd.** Em `/etc/ssh/sshd_config`, `AllowTcpForwarding` e
   `AllowStreamLocalForwarding` não podem estar como `no`. O padrão do OpenSSH é `yes`. Após
   alterar, `sudo systemctl restart sshd`.
4. **Rede.** A máquina do Lognix precisa alcançar o host na porta SSH. O host não precisa alcançar o Lognix.

## O que o Lognix faz no host

Só leitura. Toda requisição à Docker API passa por um proxy dentro do Lognix que permite apenas
`GET` em: `/_ping`, `/version`, `/info`, `/containers/json`, `/containers/{id}/json`,
`/containers/{id}/logs`, `/events`, `/images/{id}/json`, `/networks`, `/networks/{id}`. Qualquer outra requisição recebe `403` e
é registrada no log do backend com o logger `lognix.audit.docker_proxy`.

Para quem quiser garantia independente do Lognix: use um usuário SSH sem shell
(`usermod -s /usr/sbin/nologin`) e, se desejar, um proxy de socket no próprio host.

## Validação em seis etapas

| Etapa | Falha típica | O que fazer |
|---|---|---|
| 1. Alcançar o host | porta fechada, firewall, endereço errado | confira endereço e porta; libere a porta SSH para a máquina do Lognix |
| 2. Autenticar via SSH | chave não autorizada, senha errada | `ssh-copy-id`, ou confira a senha |
| 3. Fingerprint | a chave do servidor mudou desde o cadastro | se a mudança for esperada, use "Aceitar novo fingerprint" na tela do host; se não, investigue |
| 4. Encaminhar o socket | sshd com forwarding desligado, Docker parado | ajuste `AllowTcpForwarding` / `AllowStreamLocalForwarding`; `systemctl status docker` |
| 5. Falar com o Docker | usuário sem acesso ao socket | `sudo usermod -aG docker USUARIO` e abra nova sessão |
| 6. Listar containers | raro; Docker com problema | veja `docker ps` no host |

## Túnel

Um túnel SSH por host, verificado a cada 15 s. Se cair, o Lognix reconecta com espera crescente de
2 s até 5 min, indefinidamente. O estado aparece na lista de hosts e na tela do host. Fingerprint
divergente **não** reconecta sozinho: exige aceite na interface.

Ao reiniciar o backend, todos os túneis de hosts não removidos são reabertos.

## Remover um host

"Remover" oculta o host e encerra o túnel, preservando dados. Para apagar de fato,
`DELETE /api/v1/hosts/{id}?purge=true` com `{"confirm_name": "<nome>"}`. Na 0.2.0 isso apaga só o
banco; os logs no Loki entram na 0.3.0.

## Monitorar containers

Na tela do host, marque os containers e clique em "Salvar monitoramento". O Lognix regrava a
configuração do Alloy, recarrega e guarda a versão. A coleta começa **na marcação**: linhas com
timestamp anterior a dois minutos são descartadas pelo Alloy e contadas na métrica
`loki_process_dropped_lines_total{reason="lognix_before_monitoring"}`.

Containers marcados viram **projetos** e aparecem em Projetos. Os logs ficam no Loki com os labels
`host`, `host_id`, `container`, `container_id`, `compose_project` e `compose_service`.

Se um container monitorado for recriado, por exemplo por um `docker compose up` após build, o Lognix
reconhece o **redeploy** pela identidade de serviço (mesmo projeto e serviço do Compose, ou mesmo nome
sem Compose): mantém o projeto, atualiza a imagem, continua monitorando e registra um evento
`redeploy` com a imagem anterior e a nova. Nenhuma notificação é gerada.

A configuração atual do Alloy e as últimas versões aplicadas ficam visíveis na tela do host.

## Ver logs

Na tela do projeto:

- **Ao vivo**: as linhas chegam por WebSocket conforme o Alloy as envia ao Loki. Rolar para cima
  pausa o acompanhamento e um botão mostra quantas linhas novas chegaram. A tela guarda até 5 000
  linhas; acima disso, as mais antigas saem e um aviso aparece.
- **Histórico**: período de 15 minutos a 7 dias, 500 linhas por página, "carregar mais antigas" ao
  chegar ao topo. Janela máxima de consulta: 16 dias.
- **Filtro de texto**: busca literal (contém), aplicada no Loki para o histórico e no navegador para
  o ao vivo.
- Linhas com `ERROR`, `FATAL`, `Exception`, `Traceback`, `panic` ou `[error]` ganham destaque. É só
  visual; a classificação de verdade chega na 0.6.0.
- Passe o mouse sobre uma linha para ver os labels.

Logo após marcar um container a tela fica vazia até a primeira linha nova: linhas anteriores à
marcação não são coletadas.

API: `GET /api/v1/projects/{id}/logs?start=&end=&q=&limit=&direction=` e WebSocket `/ws?token=`
com mensagem `{"type":"subscribe","channel":"logs:<id>"}`.

## Inventário, eventos e notificações

Com o host conectado, o Lognix mantém dois processos por host:

- **Ouvinte de eventos**: um stream `GET /events` do Docker, filtrado por containers. Se cair, é
  reaberto a partir do último evento recebido. Eventos de containers **monitorados** são gravados:
  `start`, `die` com exit code, `oom`, `restart`, `kill`, `stop`, `pause`, `unpause`, `health_status`,
  `destroy`. Containers não monitorados só alimentam o inventário.
- **Reconciliação**: a cada 60 s, e imediatamente após eventos de `start`, `destroy`, `die`, `create` ou
  `rename`, a lista de containers é comparada com o banco.

Resultados da reconciliação:

| Situação | O que acontece |
|---|---|
| Container novo | criado como não monitorado; notificação "Novo container X em HOST" com ação **Monitorar** ou **Ignorar** |
| Container sumiu | vai para **Containers excluídos** na tela do host; deixa de ser monitorado; config do Alloy reaplicada; logs e eventos continuam acessíveis |
| Redeploy | mesmo projeto, imagem atualizada, evento `redeploy`; sem notificação |

Ao marcar um container, o Lognix o inspeciona e guarda os **nomes** das variáveis de ambiente. Valores
só são guardados para nomes seguros como `APP_VERSION`, `NODE_ENV`, `GIT_COMMIT`. Aparecem na aba
Ambiente do projeto.

Notificações também são geradas quando um host desconecta e reconecta, quando o fingerprint SSH muda
e quando o reload do Alloy falha. Ficam em Notificações até serem marcadas como vistas; "Limpar todas"
marca todas. O contador na barra lateral mostra quantas estão novas.

API: `GET /notifications`, `/notifications/history`, `/notifications/count`,
`POST /notifications/{id}/seen`, `POST /notifications/seen-all`; `GET /hosts/{id}/events`,
`GET /projects/{id}/events`, `GET /projects/excluded`, `GET /hosts/{id}/containers/excluded`.

## Ciclo de análise

Cada projeto monitorado tem um loop próprio. O ciclo consulta no Loki a janela desde o fim do ciclo
anterior (ou desde a marcação, limitada a 15 minutos no primeiro), agrupa as linhas em **padrões**
com o algoritmo Drain, classifica o nível de cada linha, grava um registro do ciclo e avalia os
**triggers**. Terminado o ciclo, espera 30 s e recomeça. Se o Loki falhar, a janela não avança e
nenhuma linha é pulada.

Classificação de nível: em linhas JSON usa-se o campo `level`, `severity`, `lvl` ou equivalente,
inclusive numérico (pino, bunyan). Em texto livre, regex por palavras inteiras como `ERROR`, `FATAL`,
`Exception`, `Traceback`, `panic`, `[error]`, `level=error`.

Triggers da v1, sem IA ainda:

| Trigger | Dispara quando |
|---|---|
| erro | a janela tem ao menos uma linha classificada como erro |
| evento Docker | `die` com exit code diferente de zero, `oom`, healthcheck `unhealthy`, ou 3 restarts em 5 min |
| anomalia | com ao menos 10 ciclos anteriores: volume acima de média + 3 desvios e 2× a média; taxa de erro idem; 3 ou mais padrões novos num ciclo |
| manual | botão **Analisar agora** no projeto, janela escolhida, limite de 1 por minuto por projeto |

Enquanto a IA não está configurada, cada trigger fica em **Insights › Ocorrências sem análise**,
com as linhas de erro da janela. A aba **Padrões** do projeto lista os templates com contagem;
**Ignorar** marca um padrão para não abrir issues no futuro. A aba **Ciclos** mostra os registros.

O **Executor**, painel no canto da tela, mostra as análises em andamento com fase e tempo.

Limitações conhecidas: o template de um padrão evolui conforme o Drain vê variações; quando muda,
nasce uma linha nova e a antiga fica com a contagem até então. Os clusters do Drain vivem em memória e
são reconstruídos a partir das amostras guardadas quando o backend reinicia.

API: `GET /projects/{id}/patterns`, `PUT /projects/{id}/patterns/{pid}/ignore`,
`GET /projects/{id}/analysis-runs`, `GET /projects/{id}/triggers`, `POST /projects/{id}/analyze`,
`GET /insights/unanalyzed`, `GET /executor`; WebSocket canal `executor`.

## Tela Sistema

Em Configurações › Sistema: versão, tempo no ar, retenção, intervalo entre ciclos, estado de
Postgres, Loki e Alloy, contadores do banco, processos em execução por host (túnel conectado,
reconexões, eventos recebidos, reaberturas do stream, último erro) e uso de disco dos volumes.

O campo **Requisições bloqueadas pelo proxy** conta quantas chamadas não permitidas à Docker API
foram recusadas desde que o backend subiu. Em operação normal fica em zero. Qualquer número acima
disso merece olhar o log do backend, logger `lognix.audit.docker_proxy`, que registra método e
caminho de cada recusa.

## Métricas

`GET /api/v1/metrics` responde no formato Prometheus. A porta do backend não é exposta: a rota só é
alcançável dentro da rede do compose. Principais séries:

| Série | O que mostra |
|---|---|
| `lognix_cycle_duration_seconds` por fase | duração do ciclo em loki, drain, persist e triggers |
| `lognix_cycles_total` por status | ciclos concluídos: ok, failed, truncated |
| `lognix_triggers_total` por tipo | triggers disparados |
| `lognix_analysis_loops` | loops de análise ativos |
| `lognix_tunnels` por estado | túneis conectados, desconectados, em erro |
| `lognix_tunnel_reconnects_total` | reconexões de túnel |
| `lognix_docker_proxy_requests_total` por desfecho | chamadas à Docker API permitidas e recusadas |
| `lognix_docker_events_total` por tipo | eventos Docker recebidos |
| `lognix_loki_query_duration_seconds` | latência das consultas ao Loki |
| `http_request_duration_seconds` por rota | latência da API |

Para ver isso em painéis, há um compose auxiliar em `measure/`, com Prometheus e Grafana. Não faz
parte da instalação padrão.

## Backup e restauração

Três coisas precisam ser salvas: o banco, os logs e a chave.

```bash
# 1. Banco: hosts, credenciais criptografadas, padrões, ocorrências
docker compose exec -T postgres pg_dump -U lognix -Fc lognix > lognix-$(date +%F).dump

# 2. Logs, volume do Loki. Pare o Loki para uma cópia consistente.
docker compose stop loki
docker run --rm -v lognix_loki-data:/data -v "$PWD":/out alpine \
  tar czf /out/loki-$(date +%F).tar.gz -C /data .
docker compose start loki

# 3. A chave. Sem ela o banco restaurado tem credenciais ilegíveis.
grep LOGNIX_SECRET_KEY .env
```

Restauração:

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U lognix -d postgres -c 'DROP DATABASE IF EXISTS lognix'
docker compose exec -T postgres psql -U lognix -d postgres -c 'CREATE DATABASE lognix'
docker compose exec -T postgres pg_restore -U lognix -d lognix < lognix-AAAA-MM-DD.dump
docker run --rm -v lognix_loki-data:/data -v "$PWD":/in alpine \
  sh -c 'rm -rf /data/* && tar xzf /in/loki-AAAA-MM-DD.tar.gz -C /data'
docker compose up -d
```

Procedimento verificado em 2026-11-24 numa instalação com 4 hosts e 20 containers: o dump
restaurou hosts, containers, padrões, ciclos e usuários, e as credenciais criptografadas
continuaram legíveis com a mesma chave.

Depois de restaurar, confira em Sistema que os três componentes estão ok e que os hosts
reconectaram. Se a chave do backup for diferente da que está no `.env`, os hosts falham na etapa de
autenticação e as credenciais precisam ser recadastradas.

## Desempenho

Medido em 2026-11-24 com 10 hosts e 100 containers monitorados, 200 linhas por janela:

| Medida | Valor |
|---|---|
| Ciclo determinístico, p95 | 948 ms |
| Latência da API, p95, regime normal | 42 ms |
| Latência da API, p95, ciclos sem pausa | 118 ms |
| Memória do backend | 206 MB |
| Banco após 2000 ciclos | 12 MB |

Botões de ajuste no `.env`, raramente necessários:

| Variável | Padrão | Para quê |
|---|---|---|
| `LOGNIX_ANALYSIS_CONCURRENCY` | 8 | ciclos de análise simultâneos |
| `LOGNIX_DB_POOL_SIZE` | 20 | conexões no pool do banco |
| `LOGNIX_DB_MAX_OVERFLOW` | 10 | conexões extras sob pico |

Aumentar a concorrência acima do número de núcleos não acelera: o trabalho é CPU e banco.

## Painel

A tela inicial resume as últimas 24 horas: linhas analisadas, linhas de erro, ocorrências, projetos
com erro na última hora e ciclos com falha. Abaixo, o estado de cada host, as notificações novas,
os projetos mais ativos e as ocorrências recentes. Tudo vem de uma chamada só, `GET /summary`, e se
atualiza a cada 20 s.

Com nenhum host cadastrado, a tela inteira vira o convite para cadastrar o primeiro.

## Configurar a IA

São duas telas. **Configurações › Provedores** guarda quem atende as chamadas; **Configurações › IA**
tem o interruptor geral e os limites por chamada.

### Provedores

Um provedor é uma conta num serviço de modelos. O Lognix suporta três tipos:

| Tipo | Credenciais | Catálogo de modelos |
|---|---|---|
| OpenRouter | chave de API | sim, com preço |
| OpenAI | chave de API, e opcionalmente URL base e organização | sim, sem preço |
| Amazon Bedrock | região, access key, secret key, e session token se for credencial temporária | não |

Dá para cadastrar mais de um do mesmo tipo — duas contas, dois orçamentos — e cada um recebe um nome
seu. As credenciais são guardadas criptografadas no banco e **nunca voltam pela API**: a tela mostra
apenas que existe um valor salvo. Deixar o campo em branco mantém o valor atual.

Um provedor fica **pronto** quando tem credencial, modelo padrão e está ativado. Só os prontos entram
na cadeia de fallback. A tabela diz em que estado cada um está e, quando o último teste falhou, mostra
o motivo na própria linha.

### A cadeia de fallback

A coluna **Ordem** é a ordem das tentativas, numerada. O 1º pronto recebe a chamada; se recusar —
chave inválida, modelo inexistente, limite de uso estourado, serviço fora —, a chamada desce para o
próximo. As setas da primeira coluna mudam a ordem, e um traço no lugar do número quer dizer que
aquele provedor está fora da cadeia.

Com um provedor só, uma queda dele deixa as ocorrências sem análise. É por isso que a tela diz isso
em voz alta quando há apenas um.

Resposta fora do formato esperado **não** desce a cadeia: ela é retentada uma vez no mesmo provedor,
porque trocar de provedor não corrige formato.

### Modelos

A seta no começo da linha abre os **modelos** daquele provedor, sem sair da tabela: os cadastrados,
com preço e janela de contexto, e um campo de busca que lista o catálogo do provedor. Escolher um
nome no catálogo cadastra o modelo — o catálogo é só para escolher, cadastrar é ato explícito.

**À mão** cadastra o que catálogo nenhum lista: um modelo do Bedrock, um perfil de inferência, um
deployment. O preço digitado ali é o que será usado para estimar o custo quando o provedor não
informar. **Atualizar preços** relê o catálogo e corrige preço e contexto do que já está cadastrado.

No menu de cada linha, **Testar agora** faz uma chamada mínima e mostra latência e custo real. Use
antes de ativar: é a forma mais rápida de saber se a credencial e o modelo estão certos.

### O interruptor geral

Em Configurações › IA. Três estados, e vale distinguir:

| Estado | Significa |
|---|---|
| nenhum provedor pronto | não há a quem chamar; ligar é recusado com uma mensagem dizendo o que falta |
| desligada | há provedor pronto, mas o interruptor está desligado |
| ligada | a IA roda quando um trigger disparar |

Na mesma tela ficam os limites por chamada — tokens de entrada, tokens de saída e chamadas simultâneas
—, que valem para todos os provedores.

O aviso sobre dados sensíveis fica fixo no topo da tela de Provedores: trechos de log saem para o
provedor escolhido e para o fabricante do modelo, sem redação automática nesta versão.

### Subindo da 0.9.0

Quem já tinha a chave do OpenRouter configurada não reconfigura nada. Na primeira subida, a chave vira
um provedor OpenRouter habilitado, com o modelo que estava escolhido, e a configuração antiga é
apagada.

## Insights

Com a IA ativa, cada ocorrência detectada pelo ciclo vira um insight. O caminho é sempre o mesmo:

```
trigger dispara → backend monta o contexto → chama o provider → valida a resposta
    → insight com evidências, ou erro registrado e notificação
```

Um insight traz severidade, título, resumo, causa provável, ação sugerida, confiança e as
**evidências**: as linhas de log, eventos e padrões que embasaram a conclusão. As evidências não são
escritas pela IA. Ela cita índices do contexto e o backend troca por linhas e eventos reais, então
não há como inventar uma evidência.

Cada insight mostra também o **contexto exato enviado ao provider** e o custo da chamada. Isso não é
enfeite: é como você confere o que saiu do seu ambiente.

Severidades, e o que significam:

| | |
|---|---|
| critical | o serviço está fora do ar ou perdendo dados agora |
| high | funcionalidade importante quebrada, ou falha repetida que vai piorar |
| medium | erros que afetam parte dos usuários ou degradam o serviço |
| low | erros isolados, sem impacto perceptível |
| info | não é um problema; é um fato que vale registrar |

Confiança abaixo de 0,4 ganha um selo de baixa confiança na interface. Insights ficam na lista até
serem marcados como vistos, um a um ou com "limpar todos", e seguem acessíveis no histórico.

### Quando a IA falha

Nada falha em silêncio. Cada tentativa é registrada com o provedor que a atendeu e o erro que
devolveu. Quando a cadeia inteira falha, o Lognix gera **uma** notificação — não uma por tentativa — e
deixa a ocorrência marcada como **sem análise**. Você vê o que não foi analisado e por quê.

Limite de uso pausa **aquele provedor** por cinco minutos, não a IA. A chamada segue para o próximo da
cadeia. Só quando todos estão pausados é que a ocorrência fica sem análise. As pausas aparecem na tela
de Consumo.

Resposta fora do esquema tem **um** retry no mesmo provedor, com o erro anexado para o modelo se
corrigir. O segundo erro encerra a tentativa naquele provedor e a chamada desce a cadeia.

## Consumo

Configurações › Consumo mostra chamadas, tokens e custo em hoje, 7 dias, 30 dias e total, quantas
caíram para o fallback e a latência média. Abaixo, uma tabela **por provedor** — chamadas, taxa de
sucesso, fallbacks, latência média, p95 e custo — que é o que permite decidir qual provedor merece ser
o principal. Depois o detalhamento por modelo, projeto, tipo de trigger e dia, e as chamadas
individuais, com filtro para ver só as que falharam. Cada chamada mostra o provedor que a atendeu e um
selo quando foi fallback.

O custo vem da resposta do provedor quando ele informa; caso contrário é estimado pelo preço
cadastrado naquele modelo, e a origem fica registrada em cada chamada. Modelo sem preço cadastrado e
provedor que não informa custo somam zero — o que aparece como consumo de graça, não como erro.

Nesta versão **não há orçamento com bloqueio**: você vê o gasto, mas o Lognix não para de chamar
sozinho. Para controlar o custo, os botões são a concorrência, os limites de tokens e, no limite,
desligar a IA.

### O que custa

A IA só é chamada quando um trigger dispara, e no máximo uma vez por ciclo por container. Um
projeto quieto não gasta nada. Um projeto com erro contínuo gasta a cada ciclo, porque esta versão
**não deduplica insights**: o mesmo erro persistente gera um insight por ciclo. Essa é a primeira
melhoria do roadmap de IA. Até lá, marcar o padrão como ignorado na aba Padrões do projeto é a
válvula de escape.

## Privacidade

Trechos de log saem do seu ambiente para o OpenRouter e, por ele, para o fabricante do modelo
escolhido. Não há redação automática nesta versão. Variáveis de ambiente nunca são enviadas por
valor, apenas por nome, exceto uma lista curta de nomes seguros como `APP_VERSION` e `GIT_COMMIT`.

O aviso fica fixo na tela de configuração da IA. Se os logs de um projeto contêm dados que não podem
sair do seu ambiente, não ative a IA.

Fora o provider de IA, nada sai: sem telemetria, sem verificação de atualização, sem chamadas a
serviços do autor.
