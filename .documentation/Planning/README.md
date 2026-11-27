# Lognix — Planejamento

> **Regra de ouro:** nada é construído antes de estar mapeado aqui. Ela valeu para tudo que existe
> hoje e continua valendo para o que vier.

**Esta área é registro, não espelho do código.** Cada documento diz o que foi decidido e quando, com
as alternativas que foram descartadas e o motivo. Para saber como o sistema se comporta **hoje**, o
lugar é [Software/](../Software/README.md); aqui se descobre por que ele se comporta assim. Um
documento que descreve uma tela que mudou depois não está errado — está datado.

Os [ADRs](02%20Arquitetura/ADR/README.md) são a exceção: decisão que cai é marcada como substituída
ou ampliada por outra, nunca apagada.

Lognix é um **analisador de logs com IA**. Mapeia instâncias (hosts), conecta-se a elas,
coleta logs de containers via **Grafana Alloy**, centraliza tudo e usa modelos de linguagem
para explicar, agrupar, detectar anomalias e sugerir causa raiz.

- **Estado:** 1.3.0 construída. A 1.0.0 fechou da fundação à análise por IA; a 1.2.0 abriu o Lognix para clientes de IA pelo MCP; a 1.3.0 deu à IA área própria na interface. As fases estão em [Fases de Construção](08%20Gestão/Fases%20de%20Construção.md)
- **Versionamento:** SemVer por label de PR. IA entrou na 0.9.0. 1.0.0 é o primeiro release público, com imagem publicada
- **Natureza:** código aberto
- **Alvo inicial:** Docker · **Alvo futuro:** Kubernetes
- **Diferencial:** diagnóstico de erro ligado ao código no GitHub, com abertura de issue
- **Stack:** Python (backend) · React + Vite + CSS (frontend) · Grafana Alloy (coleta) · infra em containers

## Áreas

| # | Área | O que define | Status |
|---|------|--------------|--------|
| 01 | [Produto](01%20Produto/README.md) | Problema, visão, escopo, personas, requisitos, jornadas, glossário | Implementado |
| 02 | [Arquitetura](02%20Arquitetura/README.md) | Componentes, fluxo de dados, stack, modelo de dados, ADRs | 17 ADRs |
| 03 | [Coleta de Logs](03%20Coleta%20de%20Logs/README.md) | Alloy, inventário e conexão de instâncias, Docker, Kubernetes | Implementado |
| 04 | [Inteligência Artificial](04%20Inteligência%20Artificial/README.md) | Casos de uso, pipeline, prompts, providers, custos, guardrails | Implementado |
| 05 | [Backend](05%20Backend/README.md) | API, autenticação, workers, integrações | Implementado |
| 06 | [Frontend](06%20Frontend/README.md) | Telas, navegação, componentes, estado, design system | Implementado |
| 07 | [Infraestrutura e Segurança](07%20Infraestrutura%20e%20Segurança/README.md) | Ambientes, compose, CI/CD, segredos, RBAC | Implementado |
| 08 | [Gestão](08%20Gestão/README.md) | Roadmap, fases, questões abertas | Implementado |
| 09 | [Integração GitHub](09%20Integração%20GitHub/README.md) | Vínculo container e repositório, leitura de código, diagnóstico, issues | Planejado, três fases a seguir |
| 10 | [Servidor MCP](10%20Servidor%20MCP/README.md) | Ferramentas, chaves, escopos e auditoria do Model Context Protocol | Implementado na 1.2.0 |

## Ciclo de vida de um documento

`Rascunho` → `Em revisão` → `Aprovado` → `Implementado` (ou `Obsoleto`)

Um documento só vai para `Aprovado` com confirmação explícita do dono do projeto. Mudança em
documento `Aprovado` exige ADR novo ou atualização do ADR existente.

`Implementado` **não** quer dizer que o texto acompanha o código daí em diante. Quer dizer que
aquela decisão virou produto, e que a descrição do comportamento atual passou a morar em
`Software/`.

## Convenções

- Idioma: **português**. Identificadores de código, labels e chaves de config: **inglês**.
- Nomes de pastas e arquivos: espaço como separador, iniciais maiúsculas.
- Toda pasta tem `README.md` com índice e status dos documentos.
- Diagramas em **Mermaid** dentro do markdown.
- Decisão não óbvia vira ADR em `02 Arquitetura/ADR/`.
- Dúvida que bloqueia código vai para `08 Gestão/Questões Abertas.md` com ID `Q-###`.
