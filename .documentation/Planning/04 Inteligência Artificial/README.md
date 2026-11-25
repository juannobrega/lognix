# 04 — Inteligência Artificial

Define o que a IA faz com os logs, como, a que custo e com quais limites.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| [Casos de Uso](Casos%20de%20Uso.md) | Os quatro casos da v1, o que a IA não faz, princípios | Rascunho para revisão |
| [Pipeline de Análise](Pipeline%20de%20Análise.md) | Do tick ao insight: contexto, redução, chamada, validação com retry, esquema, deduplicação | **Aprovado** |
| [Providers](Providers.md) | Interface AiProvider, os três tipos da 1.0.0, credenciais, cadeia de fallback, preço por modelo | **Aprovado** |
| [Prompts](Prompts.md) | Estrutura, regras, versionamento e avaliação dos prompts | **Aprovado** |
| [Custos e Limites](Custos%20e%20Limites.md) | Registro, tela de consumo, limites padrão, estimativas | **Aprovado** |
| [Guardrails](Guardrails.md) | Dados sensíveis sem redação na v1, alucinação, ações, custo, falhas, prompt injection | **Aprovado** |

## Decisões já tomadas

- **Providers:** OpenRouter, OpenAI e Amazon Bedrock, cadastrados pela interface, em cadeia de fallback ordenada pelo usuário. Toda tentativa é contabilizada em tokens, custo e quantidade, com o provedor que a atendeu. Ver [ADR 006](../02%20Arquitetura/ADR/ADR%20006%20Provider%20de%20IA%20via%20OpenRouter%20e%20Contabilização%20de%20Custos.md) e [ADR 012](../02%20Arquitetura/ADR/ADR%20012%20M%C3%BAltiplos%20Provedores%20de%20IA%20com%20Cadeia%20de%20Fallback.md).
- **A IA nunca roda sozinha.** Ela é acionada por **triggers** programáticos. O ciclo de análise avalia a janela e, quando um trigger dispara, o backend monta o contexto, chama a IA e espera a resposta antes de contar os 30 s até o próximo ciclo.
- **Trigger de erro** é o primeiro e obrigatório: a janela contém linhas classificadas como erro. O backend coleta o contexto, linhas anteriores e posteriores, eventos Docker do período, metadados do workload, monta o prompt e envia. A resposta vira um **insight** com metadados, horário, o que aconteceu e, quando houver repositório vinculado, o trecho de código suspeito.
- **Janela normal não gasta IA.** Sem trigger, a rotina só agrupa padrões e atualiza estatísticas.
- **Quatro triggers na v1**, nesta ordem de implementação:
  1. **Erro:** a janela contém linhas classificadas como erro.
  2. **Evento Docker crítico:** OOM kill, exit code diferente de zero, restart em loop.
  3. **Anomalia estatística:** desvio de volume, taxa de erro ou surgimento de padrão inédito frente ao histórico do workload.
  4. **Manual:** botão "analisar agora" na interface, sobre uma janela e workload escolhidos pelo usuário.
- **Classificação de erro em duas camadas.** Quando o log é estruturado, por exemplo JSON com campo `level`, usa-se o nível. Quando é texto livre, regex por palavras-chave como `ERROR`, `FATAL`, `Exception`, `Traceback`, `panic`. O conjunto de regex é versionado e extensível pelo usuário no roadmap.
- **Agrupamento de padrões com Drain**, por biblioteca existente, sem IA nessa etapa. A IA recebe padrões e amostras, não linhas brutas em massa.
