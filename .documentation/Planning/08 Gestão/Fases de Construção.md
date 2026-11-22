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
| 0.6.0 | **Ciclo determinístico** | Loop por container, janela variável, Drain e `Pattern`, classificador nível e regex, `AnalysisRun`, os quatro triggers gravando `TriggerFired` **sem IA**, tela de ocorrências sem análise, executor. **Em construção desde 2026-11-22** | 0.4.0, 0.5.0 | Desempenho do ciclo. Critérios do ADR 009 |
| 0.7.0 | **Medição e endurecimento** | Medição formal do ADR 009 e decisão sobre Redis; auditoria do proxy; testes de 1 h com 10 hosts e 100 containers; backup documentado | 0.6.0 | Escala da instância única |
| 0.8.0 | **Interface completa** | Painel inicial, notificações com visto e limpar todos, histórico, tela de hosts, configurações, consumo preparado | 0.6.0 | Usabilidade |
| 0.9.0 | **IA** | `AIProvider`, OpenRouter, tela de configuração com teste, pipeline de contexto e redução, esquema fechado com retry, `Insight`, `AICall`, tela de consumo, aviso de dados sensíveis | 0.8.0 | Qualidade do JSON estruturado, custo |
| 1.0.0 | **Release público** | README do projeto, documentação de instalação em `Software/`, licença, tag e release no GitHub. **Só código.** Sem imagens publicadas | 0.9.0 | Primeira impressão de quem avalia |

## 3. Depois do 1.0.0

| Versão | Fase | Entrega |
|---|---|---|
| 1.1.0 | **GitHub App** | Registro do App, configuração, vínculo de repositório com pré-preenchimento OCI, validação de repositório de código |
| 1.2.0 | **Diagnóstico de código** | Seleção de arquivos a partir do erro, IA-2, `code_diagnosis` na interface |
| 1.3.0 | **Issues** | IA-3, template, abrir, comentar, reabrir, `GithubIssue` |
| 1.x | Roadmap | Conforme [Roadmap](Roadmap.md), começando por deduplicação de insights e imagens publicadas |

**Decidido em 2026-11-21:** GitHub fica depois do 1.0.0. A Visão e Escopo foi ajustada para separar
**núcleo**, entregue no 1.0.0, de **diferencial**, entregue em 1.1.0 a 1.3.0.

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
| 1.0.0 | Software/ completo |
