# 04 — Inteligência Artificial

Define o que a IA faz com os logs, como, a que custo e com quais limites.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| [Casos de Uso](Casos%20de%20Uso.md) | Os quatro casos da v1, o que a IA não faz, princípios | Rascunho para revisão |
| [Pipeline de Análise](Pipeline%20de%20Análise.md) | Do tick ao insight: contexto, redução, chamada, validação com retry, esquema, deduplicação | Rascunho para revisão |
| [Providers](Providers.md) | Interface AIProvider, implementação OpenRouter, tela de configuração | Rascunho para revisão |
| [Prompts](Prompts.md) | Estrutura, regras, versionamento e avaliação dos prompts | Rascunho para revisão |
| [Custos e Limites](Custos%20e%20Limites.md) | Registro, tela de consumo, limites padrão, estimativas | Rascunho para revisão |
| [Guardrails](Guardrails.md) | Dados sensíveis sem redação na v1, alucinação, ações, custo, falhas, prompt injection | Rascunho para revisão |

## Decisões já tomadas

- **Provider:** só OpenRouter na v1, configurado pela interface, com abstração interna para outros no futuro. Toda chamada é contabilizada em tokens, custo e quantidade. Ver [ADR 006](../02%20Arquitetura/ADR/ADR%20006%20Provider%20de%20IA%20via%20OpenRouter%20e%20Contabilização%20de%20Custos.md).
- **A IA nunca roda sozinha.** Ela é acionada por **triggers** programáticos. A rotina de 30 s avalia a janela e, quando um trigger dispara, o backend monta o contexto e chama a IA.
- **Trigger de erro** é o primeiro e obrigatório: a janela contém linhas classificadas como erro. O backend coleta o contexto, linhas anteriores e posteriores, eventos Docker do período, metadados do workload, monta o prompt e envia. A resposta vira um **insight** com metadados, horário, o que aconteceu e, quando houver repositório vinculado, o trecho de código suspeito.
- **Janela normal não gasta IA.** Sem trigger, a rotina só agrupa padrões e atualiza estatísticas.
- **Quatro triggers na v1**, nesta ordem de implementação:
  1. **Erro:** a janela contém linhas classificadas como erro.
  2. **Evento Docker crítico:** OOM kill, exit code diferente de zero, restart em loop.
  3. **Anomalia estatística:** desvio de volume, taxa de erro ou surgimento de padrão inédito frente ao histórico do workload.
  4. **Manual:** botão "analisar agora" na interface, sobre uma janela e workload escolhidos pelo usuário.
- **Classificação de erro em duas camadas.** Quando o log é estruturado, por exemplo JSON com campo `level`, usa-se o nível. Quando é texto livre, regex por palavras-chave como `ERROR`, `FATAL`, `Exception`, `Traceback`, `panic`. O conjunto de regex é versionado e extensível pelo usuário no roadmap.
- **Agrupamento de padrões com Drain**, por biblioteca existente, sem IA nessa etapa. A IA recebe padrões e amostras, não linhas brutas em massa.
