# Arquitetura Geral

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Consolida as decisões dos ADRs 001 a 009 em uma visão única do sistema.

## 1. Contexto

```mermaid
flowchart LR
    U[Usuário] -->|navegador| FE[Lognix Frontend]
    FE --> BE[Lognix Backend]
    BE -->|SSH| H1[Host Docker 1]
    BE -->|SSH| H2[Host Docker N]
    BE -->|HTTPS| OR[OpenRouter]
    BE -->|HTTPS| GH[GitHub]
```

O Lognix roda em uma máquina com Docker. Alcança os hosts monitorados por SSH, saída apenas. Usa dois
serviços externos: OpenRouter para IA e GitHub para código e issues. Nenhum host monitorado precisa
alcançar o Lognix.

## 2. Containers do Lognix

```mermaid
flowchart TB
    subgraph Lognix["Máquina do Lognix (docker compose)"]
        FE[frontend<br/>React + Vite + TS<br/>servido por nginx]
        BE[backend<br/>FastAPI]
        PG[(postgres<br/>metadados)]
        LK[(loki<br/>logs)]
        AL[alloy<br/>coleta]
        VOL[/volume tunnels/]
    end
    FE -->|REST + WS| BE
    FE -->|tail via backend| BE
    BE --> PG
    BE -->|LogQL| LK
    BE -->|gera config, /-/reload| AL
    BE -->|cria sockets| VOL
    AL -->|lê sockets| VOL
    AL -->|loki.write| LK
```

| Container | Responsabilidade | Estado |
|---|---|---|
| frontend | Interface. Arquivos estáticos servidos por nginx, que também faz proxy de `/api` para o backend | Sem estado |
| backend | API, autenticação, supervisor de túneis, proxy somente leitura, ciclos de análise, triggers, IA, GitHub, gerador de config do Alloy | Instância única |
| postgres | Usuários, hosts, containers, insights, chamadas de IA, notificações, issues, configurações | Volume `postgres-data` |
| loki | Logs dos containers monitorados | Volume `loki-data` |
| alloy | Descobre containers via sockets espelhados, filtra os monitorados, envia ao Loki | Config gerada pelo backend |
| volume tunnels | Sockets Unix espelhados, um por host | Compartilhado entre backend e alloy |

## 3. Caminho de um log

```mermaid
sequenceDiagram
    participant D as dockerd (host remoto)
    participant T as Túnel SSH (backend)
    participant P as Proxy somente leitura (backend)
    participant A as Alloy
    participant L as Loki
    participant B as Rotina 30s (backend)
    participant F as Frontend

    A->>P: GET /containers/json (discovery)
    P->>T: repassa GET
    T->>D: via SSH
    D-->>A: lista de containers
    Note over A: discovery.relabel mantém só monitorados
    A->>P: GET /containers/{id}/logs?follow=1
    P->>T: repassa GET
    T->>D: via SSH
    D-->>A: stream de linhas
    A->>L: loki.write com labels host, container, project...
    B->>L: a cada 30s, LogQL da janela recente
    F->>B: tail ao vivo (WS)
    B->>L: tail
```

O backend nunca lê linhas de log pela Docker API. Logs vêm sempre do Loki.

## 4. Módulos do backend

```mermaid
flowchart LR
    API[API HTTP + WS] --> AUTH[Auth / Usuários]
    API --> HOSTS[Hosts e Containers]
    API --> INS[Insights e Notificações]
    API --> CFG[Configurações]
    HOSTS --> TUN[Supervisor de Túneis]
    TUN --> RO[Proxy Somente Leitura]
    HOSTS --> DOCK[Cliente Docker API]
    DOCK --> RO
    HOSTS --> ALCFG[Gerador de Config Alloy]
    SCHED[Agendador 30s] --> RUN[Rotina de Análise]
    RUN --> LOKI[Cliente Loki]
    RUN --> PAT[Padrões Drain]
    RUN --> CLS[Classificador de Erro]
    RUN --> TRG[Triggers]
    TRG --> AI[AIProvider / OpenRouter]
    AI --> COST[Contabilização]
    TRG --> GHM[GitHub App]
    EVT[Ouvinte de Eventos Docker] --> DOCK
    EVT --> TRG
    EVT --> INS
```

| Módulo | O que faz | Referência |
|---|---|---|
| Auth / Usuários | Login, JWT, cadastro | ADR 008 |
| Hosts e Containers | CRUD de hosts, validação de conexão, inventário, seleção de monitorados | Área 03 |
| Supervisor de Túneis | Abre, vigia, reconecta e encerra túneis SSH | ADR 002 |
| Proxy Somente Leitura | Único caminho para a Docker API, só `GET` | ADR 003 |
| Cliente Docker API | Inventário, inspeção, eventos | ADR 004 |
| Gerador de Config Alloy | Um bloco por host, filtro de monitorados, `/-/reload` | Área 03 |
| Ouvinte de Eventos Docker | `GET /events` por host: start, die, oom, restart. Gera notificação de container novo e alimenta triggers | Área 03 |
| Agendador | Mantém um ciclo por container monitorado, com 30 s entre o fim de um e o início do próximo | ADR 005, ADR 009 |
| Rotina de Análise | Consulta Loki, agrupa, classifica, avalia triggers | ADR 005 |
| Padrões Drain | Templates por container | Área 04 |
| Classificador de Erro | Nível estruturado ou regex | Área 04 |
| Triggers | Erro, evento crítico, anomalia, manual | Área 04 |
| AIProvider | Interface única, implementação OpenRouter | ADR 006 |
| Contabilização | Registro de cada chamada de IA | ADR 006 |
| GitHub App | Leitura de código, issues | ADR 007, área 09 |
| Insights e Notificações | Persistência, visto, limpar todos | Modelo de Dados |
| Configurações | Provider de IA, GitHub App, criptografadas | ADR 006, ADR 007 |

## 5. Fluxos principais

### 5.1 Cadastro de host

```mermaid
sequenceDiagram
    actor U as Usuário
    participant F as Frontend
    participant B as Backend
    participant H as Host remoto

    U->>F: endereço, porta, usuário SSH, chave
    F->>B: POST /hosts
    B->>H: SSH + túnel de socket
    B->>H: GET /version via proxy
    alt falha
        B-->>F: erro com motivo (SSH, permissão no socket, sem Docker)
    else sucesso
        B->>H: GET /containers/json
        B-->>F: host criado + lista de containers
        U->>F: seleciona containers a monitorar
        F->>B: PUT /hosts/{id}/containers/monitored
        B->>B: gera config Alloy, /-/reload
        B->>B: inicia ouvinte de eventos do host
    end
```

### 5.2 Ciclo de análise por container

```mermaid
flowchart TD
    S[início do ciclo do container] --> Q[LogQL: do fim da janela anterior até agora]
    Q --> D[Drain: atualiza padrões]
    D --> C[Classifica linhas: erro?]
    C --> T{Algum trigger?}
    T -->|não| STAT[Atualiza estatísticas]
    T -->|erro / evento / anomalia| CTX[Monta contexto:<br/>linhas, eventos, metadados, padrões]
    CTX --> AI[AIProvider.analyze]
    AI --> COST[Registra chamada e custo]
    AI --> INS[Cria insight]
    INS --> GH{Projeto GitHub?}
    GH -->|sim| CODE[Lê código relevante, diagnóstico, issue]
    GH -->|não| END[Insight somente imagem]
    STAT --> END2[aguarda 30 s, recomeça]
    END --> END2
    CODE --> END2
```

Cada container monitorado tem seu próprio ciclo. A IA é aguardada dentro do ciclo. Os 30 s contam a partir do fim do ciclo, IA incluída. ADR 005 revisado.

### 5.3 Container novo no host

Ouvinte de eventos recebe `start` de um container desconhecido. Backend cria o registro como
não monitorado, gera notificação "novo container X no host Y". Usuário decide. Se aceitar, entra no
fluxo de seleção e o Alloy é recarregado.

### 5.4 Túnel caído

Supervisor detecta falha. Marca host como desconectado, gera notificação, tenta reconectar com
backoff exponencial. Coleta daquele host para até reconectar. Alloy continua com os outros hosts.

## 6. Fronteiras de confiança

```mermaid
flowchart LR
    subgraph Externo
        H[Hosts remotos]
        OR[OpenRouter]
        GH[GitHub]
    end
    subgraph Lognix
        BE[backend]
    end
    BE -->|SSH, chave privada, só GET| H
    BE -->|chave OpenRouter, logs e código| OR
    BE -->|GitHub App, leitura de código, escrita em issues| GH
```

- Chaves SSH, chave do OpenRouter e chave privada do GitHub App ficam criptografadas no Postgres.
- Trechos de log e de código **saem** para o OpenRouter. Isso é inerente ao produto e precisa estar
  claro na documentação e na interface. Redação de dados sensíveis fica em Guardrails, área 04.
- Nenhum comando de alteração chega aos hosts. Proxy do ADR 003.

## 7. O que esta arquitetura ainda não cobre

- Kubernetes. A entidade Host precisa aceitar outro tipo de runtime no futuro.
- Mais de uma instância de backend. ADR 009.
- Hosts atrás de bastion/jump host. Candidato ao roadmap.
