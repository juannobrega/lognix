# ADR — Architecture Decision Records

Cada decisão não óbvia de arquitetura vira um arquivo `ADR NNN Título.md`.

## Formato

```
# ADR NNN — Título
**Status:** Proposto | Aceito | Substituído por ADR NNN | Rejeitado
**Data:** AAAA-MM-DD

## Contexto
## Decisão
## Alternativas consideradas
## Consequências
```

## Índice

| # | Título | Status |
|---|--------|--------|
| 001 | [Loki como Armazenamento de Logs](ADR%20001%20Loki%20como%20Armazenamento%20de%20Logs.md) | Aceito |
| 002 | [Coleta Remota via Túnel SSH](ADR%20002%20Coleta%20Remota%20via%20Túnel%20SSH.md) | Aceito |
| 003 | [Proxy Somente Leitura para Docker API](ADR%20003%20Proxy%20Somente%20Leitura%20para%20Docker%20API.md) | Aceito |
| 004 | [Fronteiras entre Alloy, Loki e Backend](ADR%20004%20Fronteiras%20entre%20Alloy%20Loki%20e%20Backend.md) | Aceito |
| 005 | [Ciclo de Análise e Visualização ao Vivo](ADR%20005%20Ciclo%20de%20Análise%20e%20Visualização%20ao%20Vivo.md) | Aceito |
| 006 | [Provider de IA via OpenRouter e Contabilização de Custos](ADR%20006%20Provider%20de%20IA%20via%20OpenRouter%20e%20Contabilização%20de%20Custos.md) | Aceito |
| 007 | [Integração GitHub via GitHub App](ADR%20007%20Integração%20GitHub%20via%20GitHub%20App.md) | Aceito |
| 008 | [Autenticação com JWT e Múltiplos Usuários sem Papéis](ADR%20008%20Autenticação%20com%20JWT%20e%20Múltiplos%20Usuários%20sem%20Papéis.md) | Aceito |
| 009 | [Sem Redis na Primeira Fase](ADR%20009%20Sem%20Redis%20na%20Primeira%20Fase.md) | Aceito. Medido em 2026-11-24: Redis não entra |
| 010 | [Desempenho do Ciclo de Análise](ADR%20010%20Desempenho%20do%20Ciclo%20de%20An%C3%A1lise.md) | Aceito |
| 011 | [Identidade Visual do Lognix](ADR%20011%20Identidade%20Visual%20do%20Lognix.md) | Aceito |
| 012 | [Múltiplos Provedores de IA com Cadeia de Fallback](ADR%20012%20M%C3%BAltiplos%20Provedores%20de%20IA%20com%20Cadeia%20de%20Fallback.md) | Aceito. Amplia o 006 |
| 013 | [Distribuição como Imagem Docker](ADR%20013%20Distribui%C3%A7%C3%A3o%20como%20Imagem%20Docker.md) | Proposto |
| 014 | [Configuração por Arquivo](ADR%20014%20Configura%C3%A7%C3%A3o%20por%20Arquivo.md) | Proposto |
| 015 | [Pipeline de Release e Publicação](ADR%20015%20Pipeline%20de%20Release%20e%20Publica%C3%A7%C3%A3o.md) | Proposto |
| 016 | [Deduplicação de Insights](ADR%20016%20Deduplica%C3%A7%C3%A3o%20de%20Insights.md) | Proposto |
| 017 | [Servidor MCP do Lognix](ADR%20017%20Servidor%20MCP%20do%20Lognix.md) | Aceito |

## Candidatos ainda não decididos

- Framework do backend Python
- `asyncssh` vs. binário `ssh` para os túneis
