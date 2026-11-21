# Lognix — Planejamento

> **Regra de ouro:** nada é construído antes de estar mapeado aqui.
> Código só nasce depois que o documento correspondente estiver com status `Aprovado`.

Lognix é um **analisador de logs com IA**. Mapeia instâncias (hosts), conecta-se a elas,
coleta logs de containers via **Grafana Alloy**, centraliza tudo e usa modelos de linguagem
para explicar, agrupar, detectar anomalias e sugerir causa raiz.

- **Fase atual:** planejamento (branch `dev`)
- **Natureza:** código aberto
- **Alvo inicial:** Docker · **Alvo futuro:** Kubernetes
- **Diferencial:** diagnóstico de erro ligado ao código no GitHub, com abertura de issue
- **Stack:** Python (backend) · React + Vite + CSS (frontend) · Grafana Alloy (coleta) · infra em containers

## Áreas

| # | Área | O que define | Status |
|---|------|--------------|--------|
| 01 | [Produto](01%20Produto/README.md) | Problema, visão, escopo, personas, requisitos, glossário | Em revisão |
| 02 | [Arquitetura](02%20Arquitetura/README.md) | Componentes, fluxo de dados, stack, modelo de dados, ADRs | 9 ADRs aceitos |
| 03 | [Coleta de Logs](03%20Coleta%20de%20Logs/README.md) | Alloy, inventário e conexão de instâncias, Docker, Kubernetes | Rascunhos para revisão |
| 04 | [Inteligência Artificial](04%20Inteligência%20Artificial/README.md) | Casos de uso, pipeline, prompts, providers, custos, guardrails | Decisões iniciais |
| 05 | [Backend](05%20Backend/README.md) | API, autenticação, workers, integrações | Decisões iniciais |
| 06 | [Frontend](06%20Frontend/README.md) | Telas, navegação, componentes, estado, design system | Pendente |
| 07 | [Infraestrutura e Segurança](07%20Infraestrutura%20e%20Segurança/README.md) | Ambientes, compose, CI/CD, segredos, RBAC | Pendente |
| 08 | [Gestão](08%20Gestão/README.md) | Roadmap, fases, questões abertas | Em revisão |
| 09 | [Integração GitHub](09%20Integração%20GitHub/README.md) | Vínculo container e repositório, leitura de código, diagnóstico, issues | Decisões iniciais |

## Ciclo de vida de um documento

`Rascunho` → `Em revisão` → `Aprovado` → `Implementado` (ou `Obsoleto`)

Um documento só vai para `Aprovado` com confirmação explícita do dono do projeto.
Mudança em documento `Aprovado` exige ADR novo ou atualização do ADR existente.

## Convenções

- Idioma: **português**. Identificadores de código, labels e chaves de config: **inglês**.
- Nomes de pastas e arquivos: espaço como separador, iniciais maiúsculas.
- Toda pasta tem `README.md` com índice e status dos documentos.
- Diagramas em **Mermaid** dentro do markdown.
- Decisão não óbvia vira ADR em `02 Arquitetura/ADR/`.
- Dúvida que bloqueia código vai para `08 Gestão/Questões Abertas.md` com ID `Q-###`.
