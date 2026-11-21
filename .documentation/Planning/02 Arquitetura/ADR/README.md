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

## Candidatos ainda não decididos

- Framework do backend Python
- TypeScript vs. JavaScript no frontend
- Provider de IA padrão e abstração
- Autenticação com GitHub: GitHub App vs. token pessoal
- Como vincular container a repositório e commit
- `asyncssh` vs. binário `ssh` para os túneis
