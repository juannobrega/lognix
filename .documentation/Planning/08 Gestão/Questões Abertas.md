# Questões Abertas

**Status:** Em revisão · **Atualizado:** 2026-11-21

Decisões pendentes que **bloqueiam código**. Cada uma tem um ID, a área afetada, as opções e uma
recomendação. Quando decidida, vira ADR ou vai para o documento da área, e sai desta lista.

| ID | Questão | Área | Opções | Recomendação | Status |
|----|---------|------|--------|--------------|--------|
| Q-001 | Framework do backend Python | 05 Backend | FastAPI · Django · Litestar | FastAPI, async nativo, bom para WebSocket e workers | Aberta |
| Q-002 | Banco de metadados | 02 Arquitetura | PostgreSQL · SQLite | PostgreSQL. SQLite tentador pela instalação, mas limita concorrência dos workers | Aberta |
| Q-003 | Fila e agendamento das rotinas | 05 Backend | Celery + Redis · arq + Redis · APScheduler no próprio processo | A definir após Q-001 | Aberta |
| Q-004 | TypeScript ou JavaScript no frontend | 06 Frontend | TS · JS | TypeScript | Aberta |
| Q-005 | CSS puro, CSS Modules ou outra abordagem | 06 Frontend | CSS puro · CSS Modules · Tailwind | CSS Modules: continua CSS, evita colisão de nomes | Aberta |
| Q-006 | Provider de IA padrão | 04 IA | Anthropic · OpenAI-compatível · Ollama | Anthropic como padrão, abstração para trocar, Ollama no roadmap | Aberta |
| Q-007 | Autenticação com GitHub | 09 GitHub | GitHub App · token pessoal | GitHub App para o produto, token pessoal para começar rápido | Aberta |
| Q-008 | Como vincular container a repositório e commit | 09 GitHub | Labels OCI na imagem · config manual no Lognix · ambos | Ambos: ler labels `org.opencontainers.image.source` e `revision` se existirem, permitir override manual | Aberta |
| Q-009 | Túnel SSH: biblioteca ou binário | 05 Backend | `asyncssh` · subprocesso `ssh` | A avaliar em protótipo. Binário é mais simples, biblioteca dá mais controle | Aberta |
| Q-010 | Gatilhos que acionam a IA na rotina de 30 s | 04 IA | Só erros · erros + anomalias · toda janela | Erros e anomalias. Nunca toda janela, por custo | Aberta |
| Q-011 | Deduplicação de issues | 09 GitHub | Por padrão de erro · por container+padrão · por hash do diagnóstico | Por container + padrão, com comentário na issue existente em recorrência | Aberta |
| Q-012 | Retenção padrão do Loki | 02 Arquitetura | 7 · 15 · 30 dias | 15 dias, configurável no `.env` | Aberta |
| Q-013 | Algoritmo de agrupamento de padrões | 04 IA | Drain · implementação própria · IA | Drain, biblioteca existente, sem IA nessa etapa | Aberta |
| Q-014 | Login no Lognix na v1 | 07 Segurança | Sem login · usuário e senha único · token | Usuário e senha único. Sem login expõe credenciais SSH de terceiros se a porta vazar | Aberta |
