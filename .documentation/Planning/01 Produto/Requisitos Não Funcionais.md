# Requisitos Não Funcionais

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

| ID | Categoria | Requisito | Como verificar |
|---|---|---|---|
| RNF-001 | Integridade do host | Nenhuma requisição não-GET ou fora da lista chega à Docker API de um host | Teste automatizado do proxy no CI, obrigatório |
| RNF-002 | Integridade do host | Nenhum software instalado no host além do que já existe | Revisão de código; documentação |
| RNF-003 | Instalação | Do clone ao primeiro log na tela em menos de 10 min em máquina limpa com Docker | Teste manual por release |
| RNF-004 | Desempenho | Parte determinística de um ciclo abaixo de 5 s por container com 100 containers ativos | Medição fase 0.7.0, ADR 009 |
| RNF-005 | Desempenho | p95 da API abaixo de 300 ms com 100 ciclos ativos | idem |
| RNF-006 | Desempenho | Logs ao vivo: linha visível na interface em menos de 3 s após emitida no container | Medição fase 0.4.0 |
| RNF-007 | Confiabilidade | Zero linhas perdidas em teste de 1 h com 50 containers, túnel estável | Teste fase 0.7.0 |
| RNF-008 | Confiabilidade | Túnel reconecta sozinho após queda; coleta retoma sem intervenção | Teste com derrubada forçada |
| RNF-009 | Confiabilidade | Falha em um loop não derruba outros nem a API | Teste de injeção de falha |
| RNF-010 | Segurança | Credenciais e chaves criptografadas em repouso; nunca em logs nem na API sem máscara | Revisão; teste de API |
| RNF-011 | Segurança | Só a porta do frontend exposta pelo compose padrão | Inspeção do compose no CI |
| RNF-012 | Segurança | Login com rate limit; senhas com Argon2id | Teste |
| RNF-013 | Transparência | Todo insight exibe o contexto exato enviado à IA e o custo | Teste de interface |
| RNF-014 | Custo | Nenhuma chamada de IA sem trigger; nenhuma chamada sem registro em `AICall` | Teste |
| RNF-015 | Privacidade | Sem telemetria nem chamadas a serviços do autor | Revisão; afirmação no README |
| RNF-016 | Retenção | Logs e eventos 15 dias por padrão, configurável; insights e chamadas permanentes | Configuração; teste de periódicos |
| RNF-017 | Operação | Backup e restauração documentados e testados | Fase 0.7.0 |
| RNF-018 | Manutenibilidade | Cada sistema externo acessado por um único módulo | Teste de arquitetura, import-linter |
| RNF-019 | Qualidade | Lint, tipos e testes verdes obrigatórios para merge em `main` | Proteção de branch |
| RNF-020 | Evolução | Nada no núcleo assume Docker fora dos módulos de coleta Docker | Revisão; Monitoramento Kubernetes |
| RNF-021 | Acessibilidade | Contraste AA, foco visível, navegação por teclado nas telas principais | Revisão manual |
| RNF-022 | Recursos | 10 hosts e 100 containers em 2 vCPU e 4 GB | Medição fase 0.7.0 |
