# Limites e Custos da Integração GitHub

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21 · **Fase:** 1.1.0 a 1.3.0

## 1. API do GitHub

| Limite | Valor | Como o Lognix lida |
|---|---|---|
| Requisições por instalação | 5 000 por hora, mais em organizações grandes | cache de conteúdo 24 h; busca de código limitada a 5 resultados |
| Busca de código | 10 por minuto | uma busca por diagnóstico; se exceder, pula a busca e usa só stack trace |
| Tamanho de arquivo via API de conteúdo | 1 MB | arquivos maiores só por janelas via API de blob |

## 2. Tokens de IA

| Chamada | Orçamento de entrada padrão |
|---|---|
| IA-2 diagnóstico | 20 000 tokens de código + o insight |
| IA-3 issue | o insight e o diagnóstico, cerca de 3 000 |

Registrados em `AICall` com `purpose` próprio. A tela de consumo separa.

## 3. Custo por erro em projeto GitHub

Na v1, um erro em projeto GitHub pode custar até três chamadas: IA-1, IA-2, IA-3. Com deduplicação
ausente, erro persistente repete as três a cada ciclo, mas a issue só recebe um comentário por hora.
A deduplicação de insights do roadmap reduz isso para uma vez por ocorrência nova.

## 4. Privacidade

Código-fonte sai para o OpenRouter. O aviso de dados sensíveis passa a mencionar código
explicitamente quando o GitHub está configurado.
