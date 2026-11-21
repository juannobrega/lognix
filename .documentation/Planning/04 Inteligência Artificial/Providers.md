# Providers de IA

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Base: ADR 006.

## 1. Abstração

Toda chamada passa por `AIProvider`, definida em [Pipeline de Análise](Pipeline%20de%20Análise.md) seção 4.
O resto do backend não conhece OpenRouter.

## 2. OpenRouter, única implementação da v1

| Aspecto | Decisão |
|---|---|
| Endpoint | API de chat compatível com OpenAI do OpenRouter |
| Autenticação | chave do usuário, cadastrada na interface, criptografada em `Setting` |
| Modelo | escolhido pelo usuário em lista obtida da API de modelos do OpenRouter, com busca. Guardado em `Setting` |
| Modelo padrão sugerido | definido na construção, após teste com os prompts reais. Critério: melhor relação qualidade e custo em JSON estruturado |
| Saída JSON | usa o modo de resposta estruturada quando o modelo anuncia suporte; caso contrário, só instrução no prompt |
| Custo | lido da resposta quando o OpenRouter devolver. Caso contrário, estimado pela tabela de preços do modelo, obtida da API de modelos e cacheada por 24 h |
| Cabeçalhos de atribuição | o OpenRouter aceita cabeçalhos identificando o app. Enviar nome e URL do projeto Lognix |
| Timeout | 60 s por chamada |
| Retry de rede | 2 tentativas com backoff em erro 5xx ou timeout. Diferente do retry de esquema |
| Rate limit | respeita 429 com espera pelo cabeçalho de retry. Acima de 3 em 1 minuto, pausa IA por 5 min e notifica |

## 3. Tela de configuração

- Campo da chave, com botão "testar": faz uma chamada mínima e mostra modelo, latência e custo.
- Seletor de modelo com busca, mostrando preço por milhão de tokens de entrada e saída.
- Orçamento de entrada por chamada e concorrência, com padrões. Ver Custos e Limites.
- Estado: "IA ativa" ou "IA desativada, motivo". Sem chave, o Lognix funciona sem IA e diz isso.

## 4. Roadmap

Anthropic e OpenAI diretos, Azure, Bedrock, Ollama local. Cada um é uma implementação de `AIProvider`.
Nada no núcleo muda.
