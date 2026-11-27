# Fases de Construção

**Status:** Em revisão · **Atualizado:** 2026-11-21

Ordem de implementação, mapeada em versões. Decisões de 2026-11-21: a IA entra na **0.9.0**; a **1.0.0**
é o primeiro release público e, por ora, publica **apenas o código**, sem imagens Docker publicadas.

## 1. Regras

- Trabalho acontece na branch `dev`. Nada é commitado direto em `main`.
- Cada fase vira um ou mais pull requests de `dev` para `main`, com label de release. Ver [CI/CD](../07%20Infraestrutura%20e%20Segurança/CI%20CD.md).
- Versão é SemVer. Antes de 1.0.0, cada fase concluída é um `release:minor`. Correções dentro da fase são `release:patch`.
- Uma fase só começa quando os documentos de planejamento que ela implementa estão `Aprovado`.
- Toda fase termina com a documentação em `Software/` atualizada para o que foi construído.

## 2. Fases

| Versão | Fase | Entrega | Depende de | Risco que ataca |
|---|---|---|---|---|
| 0.1.0 | **Fundação** | Monorepo, `docker compose` com backend, frontend, postgres; FastAPI com saúde, migrações, login JWT, cadastro de usuários; shell do React com login e layout. **Construída em 2026-11-21 na branch `dev`, aguardando PR para `main`** | — | Base |
| 0.2.0 | **Hosts e túneis** | Cadastro de host com autenticação SSH completa, validação em etapas, fingerprint, supervisor de túneis, proxy somente leitura com testes, decisão `asyncssh` vs `ssh`. **Construída em 2026-11-21 na branch `dev`.** Validada ponta a ponta com sshd real: 6 etapas, proxy bloqueando mutações, reconexão automática | 0.1.0 | Túnel SSH e socket espelhado. **Maior risco técnico** |
| 0.3.0 | **Coleta** | Loki e Alloy no compose, gerador de config por host com filtro de monitorados, recarga atômica, `AlloyConfigVersion`, seleção de containers, coleta a partir da marcação, verificação dos itens de protótipo do Alloy. **Construída em 2026-11-21 na branch `dev`.** Validada ponta a ponta: marcação → config gerada → reload → linhas no Loki só após a marcação | 0.2.0 | Comportamento do Alloy sobre túnel, início da leitura em "agora" |
| 0.4.0 | **Logs na interface** | Tela de projeto com histórico via LogQL e ao vivo via tail por WebSocket, filtros, estado vazio pós-marcação explicado. **Construída em 2026-11-21 na branch `dev`.** Validada: histórico, filtro de texto e tail ao vivo por WebSocket pela porta pública | 0.3.0 | Volume de dados no frontend |
| 0.5.0 | **Inventário e eventos** | Reconciliação de inventário, ouvinte de eventos por host, `DockerEvent`, notificação de container novo, containers excluídos, redeploy por identidade de serviço, inspeção com variáveis só por nome. **Construída em 2026-11-22 na branch `dev`** | 0.3.0 | Confiabilidade do stream de eventos |
| 0.6.0 | **Ciclo determinístico** | Loop por container, janela variável, Drain e `Pattern`, classificador nível e regex, `AnalysisRun`, os quatro triggers gravando `TriggerFired` **sem IA**, tela de ocorrências sem análise, executor. **Construída em 2026-11-22 na branch `dev`** | 0.4.0, 0.5.0 | Desempenho do ciclo. Critérios do ADR 009 |
| 0.7.0 | **Medição e endurecimento** | Medição formal do ADR 009 e decisão sobre Redis; auditoria do proxy; testes com 10 hosts e 100 containers; backup documentado. **Construída em 2026-11-24.** Medição aprovou os três critérios; Redis fica fora. Ver ADR 009 e ADR 010 | 0.6.0 | Escala da instância única |
| 0.8.0 | **Interface completa** | Painel inicial, notificações com visto e limpar todos, histórico, tela de hosts, configurações, consumo preparado. **Construída em 2026-11-24** | 0.6.0 | Usabilidade |
| 0.9.0 | **IA** | `AIProvider`, OpenRouter, tela de configuração com teste, pipeline de contexto e redução, esquema fechado com retry, `Insight`, `AICall`, tela de consumo, aviso de dados sensíveis. **Construída em 2026-11-24** | 0.8.0 | Qualidade do JSON estruturado, custo |
| 1.0.0 | **Release público** | README do projeto, SECURITY, CONTRIBUTING, templates de issue e PR, documentação em `Software/`, licença Apache 2.0, identidade visual própria, **múltiplos provedores de IA com cadeia de fallback** (OpenRouter, OpenAI, Bedrock) e observabilidade por provedor. **Só código.** Sem imagens publicadas. **Preparada em 2026-11-25**, validada com instalação limpa a partir do clone | 0.9.0 | Primeira impressão de quem avalia |

## 3. Depois do 1.0.0

| Versão | Fase | Entrega |
|---|---|---|
| 1.1.0 | **Endurecimento** | Troca de senha pela própria conta, remoção de código morto, testes HTTP dos quatro provedores de IA, deduplicação de insights em módulo próprio. **Construída em 2026-11-27** |
| 1.2.0 | **Servidor MCP** | Transporte HTTP montado em `/mcp`, dez ferramentas, chaves com escopo e auditoria, aba MCP nas configurações. **Construída em 2026-11-27.** Ver [ADR 017](../02%20Arquitetura/ADR/ADR%20017%20Servidor%20MCP%20do%20Lognix.md) e a [área 10](../10%20Servidor%20MCP/README.md) |
| 1.3.0 | **IA como área própria** | A IA sai de dentro de Configurações e vira grupo próprio, com Provedores, Consumo e MCP; interruptor geral do servidor MCP, desligado por padrão. **Construída em 2026-11-27** |
| 1.4.0 | **Descoberta de atualização** | Verificação opcional contra o registro de imagens, desligada por padrão, com aviso de versão nova e o comando pronto; endereço do MCP derivado da requisição em vez do arquivo. **Construída em 2026-11-27.** Ver [ADR 018](../02%20Arquitetura/ADR/ADR%20018%20Verificação%20de%20Atualização%20Opcional.md) |
| a seguir, 1 de 3 | **GitHub App** | Registro do App, configuração, vínculo de repositório com pré-preenchimento OCI, validação de repositório de código |
| a seguir, 2 de 3 | **Diagnóstico de código** | Seleção de arquivos a partir do erro, IA-2, `code_diagnosis` na interface |
| a seguir, 3 de 3 | **Issues** | IA-3, template, abrir, comentar, reabrir, `GithubIssue` |
| 1.x | Roadmap | Conforme [Roadmap](Roadmap.md), começando por canais de notificação |

**Decidido em 2026-11-27:** as fases do diferencial deixam de ter número de versão e passam a ter
ordem. Renumerar três documentos a cada minor que entra na frente é trabalho que só produz
chance de erro — e já produziu: o MCP saiu como 1.2.0, não 1.1.0, porque um release entrou no
meio. Número é para o que foi construído; o que vem tem ordem.

**Decidido em 2026-11-27:** o MCP entra antes do GitHub App. O motivo é sequência de valor: o MCP aproveita tudo que já existe — inventário, logs,
padrões, insights — e não depende de nada novo, enquanto o GitHub App começa por autenticação e
vínculo antes de entregar a primeira resposta útil.

**Decidido em 2026-11-21:** GitHub fica depois do 1.0.0. A Visão e Escopo foi ajustada para separar
**núcleo**, entregue no 1.0.0, de **diferencial**, entregue nas três fases seguintes.

## 4. O que cada fase precisa ter aprovado antes de começar

| Fase | Documentos |
|---|---|
| 0.1.0 | Stack Tecnológica, ADR 008, Backend/Estrutura do Projeto, Infra/Ambientes, Infra/CI CD |
| 0.2.0 | ADR 002, ADR 003, Inventário e Conexão de Instâncias, Modelo de Dados (Host, TunnelState) |
| 0.3.0 | ADR 001, ADR 004, Grafana Alloy, Modelo de Dados (Container, AlloyConfigVersion) |
| 0.4.0 | Frontend/Mapa de Telas, Frontend/Telas Detalhadas (projeto), Backend/API (logs) |
| 0.5.0 | Monitoramento Docker, Modelo de Dados (DockerEvent, Notification) |
| 0.6.0 | ADR 005, ADR 009, Pipeline de Análise (sem IA), Casos de Uso |
| 0.7.0 | ADR 009, Infra/Observabilidade do Lognix, Segurança |
| 0.8.0 | Frontend completo |
| 0.9.0 | Área 04 inteira, ADR 006 |
| 1.0.0 | Software/ completo, ADR 011, ADR 012 |
| 1.2.0 | ADR 017, área 10 inteira |
| 1.3.0 | Frontend/Mapa de Telas |
| 1.4.0 | ADR 018 |
