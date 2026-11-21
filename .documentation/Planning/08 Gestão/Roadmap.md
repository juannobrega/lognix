# Roadmap

**Status:** Em revisão · **Atualizado:** 2026-11-21

Este arquivo registra **tudo que foi deliberadamente deixado fora da v1** e as melhorias possíveis
identificadas durante o planejamento. Nada aqui tem data. A ordem dentro de cada bloco é por valor
percebido, não por compromisso.

## v1 — Escopo fechado

Resumo do que entra. Detalhes em [Visão e Escopo](../01%20Produto/Visão%20e%20Escopo.md).

- Cadastro de hosts Docker por SSH, nada instalado no host
- Coleta pelo Alloy via túnel, armazenamento no Loki, somente leitura garantido
- Inventário de containers com estado e eventos
- Rotina de análise a cada 30 s: padrões, erros, anomalias
- Visualização de logs ao vivo e histórico
- Insights de IA acionados por triggers, provider OpenRouter, custos contabilizados
- Login com JWT e cadastro de usuários, sem papéis
- Diagnóstico de código via GitHub App e abertura, comentário e reabertura de issues. Fase posterior ao núcleo
- Instalação por `docker compose up`
- Acesso único, sem permissionamento

## Pós-v1 — Melhorias possíveis

### Plataformas
- **Kubernetes.** Monitorar nós e pods. Exige abstração de instância neutra desde a v1.
- **Docker Swarm.** Provavelmente barato depois do Docker puro.
- **Podman.** Compatível com a Docker API, validar.

### Coleta
- **Alloy como agente no host.** Para instalações com centenas de hosts, onde o túnel SSH não escala. Opcional, nunca obrigatório.
- **Alloy `remotecfg`.** Agentes buscando config do Lognix em vez de receber por push.
- **Métricas básicas de container.** CPU, memória, rede, via `cadvisor` do Alloy, para correlação com logs.
- **Intervalo da rotina de análise configurável.** Hoje fixo em 30 s.
- **Descoberta de hosts.** Importar de provedores de nuvem, varredura de rede, inventário externo.
- **Bastion / jump host** para alcançar hosts sem SSH direto.
- **Apagar host de verdade**, incluindo logs no Loki, como operação separada da remoção. Pode entrar ainda na v1 se barato.

### Alertas e ações
- **Canais de notificação.** Slack, Discord, e-mail, webhook genérico, Telegram.
- **Regras de alerta configuráveis.** Hoje os gatilhos são fixos.
- **Ações no host.** Reiniciar container, por exemplo. Exigiria abandonar o somente leitura de forma explícita e opt-in. Avaliar com muito cuidado.
- **Silenciamento e janelas de manutenção.**

### Integração com código
- **GitLab, Bitbucket, Gitea.**
- **Sugestão de correção.** Além de apontar o trecho, propor o diff. Possivelmente abrir PR.
- **Comentar em PR existente** quando o erro vem de um deploy recente.
- **Correlação com deploys.** Saber que o erro começou após o commit X.

### IA
- **Deduplicação de insights.** Erro persistente hoje gera insight e chamada de IA a cada ciclo. Primeira melhoria de IA a fazer. Decidido fora da v1 em 2026-11-21.
- **Intervalo entre ciclos configurável.** Hoje 30 s fixo.
- **Outros providers além do OpenRouter.** Anthropic e OpenAI diretos, Azure, Bedrock.
- **Modelo local via Ollama** como alternativa sem custo externo.
- **Chat sobre logs** em linguagem natural, com histórico por investigação.
- **Aprendizado de padrões normais** por serviço para reduzir falsos positivos.
- **Embeddings de logs** para busca semântica.
- **Orçamento de IA** com alerta e bloqueio opcional por período.
- **Redação de dados sensíveis** antes do envio ao provider: chaves, tokens, cartões, e-mails, sempre ligada, com regex extra configurável. Decidido fora da v1 em 2026-11-21.

### Produto e acesso
- **Permissionamento e papéis.** Admin, operador, leitor. Visibilidade por host.
- **Autenticação externa.** OAuth GitHub, Google, OIDC. Hoje é usuário e senha com JWT.
- **Multi-tenant.** Organizações isoladas.
- **Internacionalização.** Interface e saída da IA em outros idiomas. Hoje só português.
- **Auditoria.** Quem fez o quê, incluindo todas as chamadas à Docker API.
- **Retenção configurável por host ou container.**

### Operação do próprio Lognix
- **Redis e fila dedicada** se a medição do ADR 009 mostrar necessidade.
- **Alta disponibilidade.** Hoje é instância única.
- **Backup e restauração** de Postgres e Loki.
- **Imagens oficiais publicadas** e release versionado.
- **Helm chart** quando houver suporte a Kubernetes.
- **Modo demo** com dados sintéticos para quem quer avaliar sem cadastrar host.

## Ideias registradas sem avaliação

Lugar para anotar rápido. Mover para um bloco acima quando avaliadas.

- (vazio)
