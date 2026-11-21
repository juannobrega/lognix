# Casos de Uso de IA

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

O que a IA faz no Lognix e, igualmente importante, o que ela não faz. A IA nunca roda sozinha: só por trigger.

## 1. Casos de uso da v1

| ID | Caso | Trigger | Entrada | Saída |
|---|---|---|---|---|
| IA-1 | **Explicar um erro** | erro, evento crítico, anomalia, manual | contexto da janela, seção 2 do Pipeline | Insight: severidade, título, resumo, causa provável, ação sugerida, evidências |
| IA-2 | **Diagnosticar no código** | IA-1 concluído em projeto do tipo GitHub | insight de IA-1 + arquivos relevantes do repositório | `code_diagnosis`: arquivo, trecho, linhas, explicação, confiança |
| IA-3 | **Redigir issue** | IA-2 concluído, ou IA-1 em projeto GitHub sem diagnóstico de código | insight + diagnóstico | título e corpo em Markdown para a issue |
| IA-4 | **Análise manual** | botão "analisar agora" | janela e projeto escolhidos pelo usuário | igual a IA-1 |

IA-2 e IA-3 pertencem à fase GitHub, posterior ao núcleo. ADR 007.

## 2. O que a IA não faz na v1

- Não classifica linhas como erro. Isso é nível estruturado ou regex, sem IA.
- Não agrupa padrões. Isso é Drain.
- Não detecta anomalia. Isso é estatística sobre `AnalysisRun` e `Pattern`.
- Não resume janelas normais. Sem trigger, sem IA.
- Não conversa. Chat sobre logs está no roadmap.
- Não propõe diff nem abre PR. Roadmap.
- Não executa nada. Nenhuma saída da IA vira ação automática além de abrir, comentar ou reabrir issue.

## 3. Princípios

1. **Determinístico antes de probabilístico.** Tudo que dá para resolver com regra, resolve-se com regra. A IA recebe trabalho pré-digerido.
2. **Explicável.** Todo insight carrega as evidências: linhas, eventos e, no caso de código, o trecho. O usuário vê de onde a conclusão saiu.
3. **Esquema fechado.** A IA responde JSON em esquema fixo. Fora do esquema é retry. Ver Pipeline seção 5.
4. **Custo por trigger, visível.** Cada chamada registrada. Ver Custos e Limites.
5. **Falha silenciosa é proibida.** Erro de IA vira notificação `ai_error`, nunca insight vazio nem ausência de insight sem explicação.
