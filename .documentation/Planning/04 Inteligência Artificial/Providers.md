# Providers de IA

**Status:** Aprovado em 2026-11-24 · **Atualizado:** 2026-11-25

Base: ADR 006 e [ADR 012](../02%20Arquitetura/ADR/ADR%20012%20M%C3%BAltiplos%20Provedores%20de%20IA%20com%20Cadeia%20de%20Fallback.md).
A seção 2 descreve o OpenRouter, que foi a única implementação até a 0.9.0. A seção 5 descreve o que
a 1.0.0 fez: três tipos de provedor, cadeia de fallback e credenciais por provedor.

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

## 3.1 Implementado na 0.9.0

- `AiProvider` é um `Protocol`; `OpenRouterProvider` é a única implementação. O resto do backend
  não importa nada de `openrouter.py`.
- `usage: {include: true}` no corpo faz o OpenRouter devolver o custo real. Quando não vem, o custo
  é estimado pela tabela de preços obtida de `/models`, e `cost_source` registra qual foi.
- `response_format` com `json_schema` e `strict` quando o modelo suporta; o esquema também vai no
  prompt, então modelos sem suporte continuam funcionando.
- Cabeçalhos `HTTP-Referer` e `X-Title` identificam o Lognix, como o OpenRouter pede.
- Erros com tratamento distinto: 401 e 403 falam da chave, 404 fala do modelo, 5xx e rede têm duas
  tentativas, 429 pausa a IA por cinco minutos.
- O provider é recriado quando a chave muda, sem reiniciar o backend.

## 4. Roadmap

Anthropic direto, Azure, Ollama local. Cada um é uma implementação de `AiProvider` mais uma entrada em
`PROVIDER_LABEL`, `CREDENTIAL_FIELDS` e `HAS_CATALOG`. Nada no núcleo muda.

## 5. Implementado na 1.0.0: três tipos e cadeia de fallback

### 5.1 Tipos

| Tipo | Transporte | Credenciais | Catálogo |
|---|---|---|---|
| OpenRouter | API de chat compatível com OpenAI | `api_key` | sim, `/models` com preço |
| OpenAI | a mesma API de chat, outra URL base | `api_key`, `base_url` opcional, `organization` opcional | sim, `/models` sem preço |
| Amazon Bedrock | Converse API, `POST /model/{modelId}/converse` | `region`, `access_key_id`, `secret_access_key`, `session_token` opcional | não |

OpenRouter e OpenAI compartilham a implementação do corpo da requisição. O Bedrock não: o formato da
Converse API é outro (`messages[].content[].text`, `system[]`, `inferenceConfig`), não existe
`response_format` universal — o esquema vai só no prompt —, e a autenticação é assinatura SigV4 feita
com `botocore.auth.SigV4Auth` sobre o `httpx`, sem trazer o `boto3`. O Bedrock também não devolve
custo, só `usage.inputTokens` e `usage.outputTokens`: o custo sai do preço cadastrado no modelo.

### 5.2 Credenciais

Cada tipo declara seus campos em `CREDENTIAL_FIELDS`, com rótulo, obrigatoriedade, se é segredo, e um
texto de ajuda. `GET /settings/ai/providers/kinds` publica isso e a interface monta o formulário. As
credenciais de um provedor viram um bloco JSON único, criptografado com AES-GCM e o id do provedor no
AAD. O que a API devolve é `credential_keys`, a lista de campos preenchidos; valor nenhum sai.

### 5.3 Cadeia de fallback

A ordem é a coluna `priority`, editável pelo usuário. Um provedor entra na cadeia quando está
habilitado, tem credencial e tem modelo padrão. A chamada vai ao primeiro; erro de credencial, modelo
inexistente, limite de uso ou indisponibilidade passam a vez ao seguinte. Resposta fora do esquema é
retentada uma vez **no mesmo provedor** e não desce a cadeia. Cada tentativa é uma linha em
`ai_calls` com `provider_id`, `attempt` e `fell_back`. Uma cadeia inteira que falha gera **uma**
notificação, não uma por tentativa.

Limite de uso pausa aquele provedor por cinco minutos, não a IA inteira. Só quando todos os
provedores da cadeia estão pausados é que a ocorrência fica sem análise.

### 5.4 Modelos e preço

`ai_models` guarda os modelos cadastrados em cada provedor, com preço de entrada e saída por milhão de
tokens e janela de contexto. Para os tipos com catálogo, a interface lista os modelos do provedor e o
usuário cadastra os que quer; "Atualizar preços" relê o catálogo e corrige preço e contexto do que já
está cadastrado. Para o Bedrock, e para perfis de inferência ou deployments que catálogo nenhum lista,
o cadastro é à mão, com o preço digitado.

Quando o provedor informa o custo na resposta, é esse que vale (`cost_source = provider`). Quando não
informa, o custo vem do preço cadastrado (`cost_source = estimated`). Modelo sem preço cadastrado soma
zero, e a tela de consumo diz isso em palavras.

### 5.5 Migração da 0.9.0

Na primeira subida da 1.0.0, se houver chave do OpenRouter em `settings` e nenhum provedor cadastrado,
ela vira um provedor OpenRouter habilitado com o modelo que estava configurado, e as linhas antigas
são apagadas — o que também impede o import de rodar duas vezes. Quem subir de versão não reconfigura
nada.
