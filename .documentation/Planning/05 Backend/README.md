# 05 — Backend

Define o serviço Python que orquestra tudo.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| [Estrutura do Projeto](Estrutura%20do%20Projeto.md) | Monorepo, pacote por domínio, loops, .env, testes | **Aprovado** |
| [API](API.md) | Convenções, todos os endpoints por domínio, canais WebSocket, limites | Rascunho para revisão |
| [Autenticação e Autorização](Autenticação%20e%20Autorização.md) | Fluxo, tokens, senhas, preparação para RBAC, proteções | Rascunho para revisão |
| [Workers e Tarefas](Workers%20e%20Tarefas.md) | Inventário de loops, LoopManager, ciclo em detalhe, periódicos, medição | Rascunho para revisão |
| [Integração com Loki](Integração%20com%20Loki.md) | Operações, seletores, paginação, tail, labels, config do Loki | Rascunho para revisão |

## Decisões já tomadas

- **Sem Redis na primeira fase.** Um loop async por container para o ciclo de análise, APScheduler para tarefas periódicas, tudo no processo do backend. Condicionado a medição com critérios definidos. Ver [ADR 009](../02%20Arquitetura/ADR/ADR%20009%20Sem%20Redis%20na%20Primeira%20Fase.md).
- **Autenticação com JWT**, cadastro de usuários pela interface, sem papéis. Ver [ADR 008](../02%20Arquitetura/ADR/ADR%20008%20Autenticação%20com%20JWT%20e%20Múltiplos%20Usuários%20sem%20Papéis.md).
- **Túnel SSH: `asyncssh`.** Decidido e implementado na 0.2.0. Motivos: suporta senha, chave e chave com passphrase sem binário externo; abre sockets Unix remotos nativamente; e permite obter a chave do servidor antes de autenticar, de modo que nenhuma credencial é enviada a um servidor cujo fingerprint não bate com o registrado.
