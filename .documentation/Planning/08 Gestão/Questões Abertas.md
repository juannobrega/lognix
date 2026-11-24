# Questões Abertas

**Status:** Em revisão · **Atualizado:** 2026-11-21

Decisões pendentes que **bloqueiam código**. Cada uma tem um ID, a área afetada, as opções e uma
recomendação. Quando decidida, vira ADR ou vai para o documento da área, e sai desta lista.

| ID | Questão | Área | Opções | Recomendação | Status |
|----|---------|------|--------|--------------|--------|
| — | Nenhuma questão aberta no momento | | | | |

## Decididas

Movidas para ADR ou documento de área. Mantidas aqui só como histórico.

| ID | Questão | Área | Decisão |
|----|---------|------|---------|
| Q-003 | Fila e agendamento das rotinas | 05 Backend | Sem Redis. APScheduler e async no processo, condicionado a medição. ADR 009 |
| Q-006 | Provider de IA padrão | 04 IA | OpenRouter único provider, configurado na interface, abstração interna, custos e chamadas contabilizados. ADR 006 |
| Q-007 | Autenticação com GitHub | 09 GitHub | GitHub App. Integração entra em fase posterior ao núcleo. ADR 007 |
| Q-008 | Como vincular container a repositório e commit | 09 GitHub | Usuário vincula workload a repositório de código. Labels OCI pré-preenchem. Sem repositório, workload é somente imagem. GitOps não aceito. Área 09 |
| Q-010 | Gatilhos que acionam a IA na rotina de 30 s | 04 IA | Triggers programáticos. Trigger de erro obrigatório: contexto do log, eventos e metadados viram prompt, resposta vira insight. Janela normal não gasta IA. Área 04 |
| Q-011 | Deduplicação de issues | 09 GitHub | Uma issue por workload e padrão. Recorrência comenta. Fechada e voltou, reabre. Área 09 |
| Q-014 | Login no Lognix na v1 | 07 Segurança | Login com usuário e senha, JWT, cadastro de usuários, sem papéis. ADR 008 |
| Q-015 | Triggers de IA além do erro na v1 | 04 IA | Os quatro: erro, evento Docker crítico, anomalia estatística, manual. Área 04 |
| Q-016 | Como as linhas são classificadas como erro | 04 IA | Nível quando o log é estruturado, regex por palavras-chave como fallback. Área 04 |
| Q-001 | Framework do backend Python | 05 Backend | FastAPI. Stack Tecnológica |
| Q-002 | Banco de metadados | 02 Arquitetura | PostgreSQL. Stack Tecnológica |
| Q-004 | TypeScript ou JavaScript no frontend | 06 Frontend | TypeScript. Stack Tecnológica |
| Q-005 | CSS puro, CSS Modules ou outra abordagem | 06 Frontend | CSS Modules, mantido. Os componentes difíceis passaram a vir do Radix na 0.9.1. Stack Tecnológica e ADR 011 |
| Q-009 | Túnel SSH: biblioteca ou binário | 05 Backend | **asyncssh**, decidido na 0.2.0: senha, chave e passphrase sem binário externo, encaminhamento de socket Unix nativo, e a chave do servidor é obtida antes de autenticar, o que torna a verificação de fingerprint segura |
| Q-012 | Retenção padrão do Loki | 02 Arquitetura | 15 dias, configurável no .env. Stack Tecnológica |
| Q-013 | Algoritmo de agrupamento de padrões | 04 IA | Drain via biblioteca, sem IA. Área 04 |
