# 04 — Inteligência Artificial

Define o que a IA faz com os logs, como, a que custo e com quais limites.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| Casos de Uso | Resumo, agrupamento de padrões, anomalias, causa raiz, perguntas em linguagem natural | A criar |
| Pipeline de Análise | Do LogQL ao insight: seleção, redução, prompt, saída estruturada, rastreabilidade | A criar |
| Providers | Abstração de provider, modelos suportados, fallback, modelo local | A criar |
| Prompts | Catálogo versionado de prompts por caso de uso | A criar |
| Custos e Limites | Estimativa por chamada, cotas, orçamento por usuário/organização | A criar |
| Guardrails | Dados sensíveis, redação, alucinação, o que a IA nunca faz | A criar |

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
