# 05 — Backend

Define o serviço Python que orquestra tudo.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| Estrutura do Projeto | Organização de módulos, camadas, convenções | A criar |
| API | Endpoints REST, WebSocket/SSE, contratos, versionamento | A criar |
| Autenticação e Autorização | Usuários, sessões, papéis, permissões | A criar |
| Workers e Tarefas | Jobs assíncronos: provisionamento, análise de IA, detecção de anomalias | A criar |
| Integração com Loki | Cliente LogQL, paginação, limites | A criar |

## Decisões já tomadas

- **Sem Redis na primeira fase.** APScheduler para a rotina de 30 s, tarefas async no processo do backend. Condicionado a medição com critérios definidos. Ver [ADR 009](../02%20Arquitetura/ADR/ADR%20009%20Sem%20Redis%20na%20Primeira%20Fase.md).
- **Autenticação com JWT**, cadastro de usuários pela interface, sem papéis. Ver [ADR 008](../02%20Arquitetura/ADR/ADR%20008%20Autenticação%20com%20JWT%20e%20Múltiplos%20Usuários%20sem%20Papéis.md).
- **Túnel SSH:** a escolha entre `asyncssh` e o binário `ssh` como subprocesso é decidida em protótipo no início da construção. Critérios: reconexão confiável, encaminhamento de socket Unix, consumo de memória por túnel.
