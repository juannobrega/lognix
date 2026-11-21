# Custos e Limites

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Base: ADR 006. Toda chamada é contabilizada e visível.

## 1. O que é registrado

Entidade `AICall`, Modelo de Dados: modelo, propósito, tokens de entrada e saída, custo, origem do
custo, latência, status, trigger, insight, versão do prompt.

## 2. Tela de consumo

| Visão | Conteúdo |
|---|---|
| Resumo | chamadas, tokens e custo em hoje, 7 dias, 30 dias, total |
| Por host e por projeto | tabela ordenável por custo |
| Por tipo de trigger | quanto custa erro, evento, anomalia, manual |
| Por propósito | analyze, code_diagnosis, issue_text |
| Linha do tempo | custo por dia, últimos 30 dias |
| Falhas | chamadas com erro, com motivo, e retries de esquema |

## 3. Limites na v1

| Limite | Padrão | Configurável |
|---|---|---|
| Tokens de entrada por chamada | 12 000 | sim |
| Tokens de saída por chamada | 1 500 | sim |
| Chamadas de IA concorrentes | 3 | sim |
| Deduplicação de insight | 30 min por container e conjunto de padrões | sim |
| Pausa após rate limit | 5 min | não |

## 4. Orçamento

Na v1, **sem orçamento com bloqueio**. O usuário vê o gasto, mas o Lognix não para de chamar. Motivo:
parar a IA silenciosamente é pior que gastar. Orçamento com alerta e com bloqueio opcional está no
roadmap.

## 5. Estimativa de referência

Para dimensionar expectativa, com contexto médio de 8 000 tokens de entrada e 600 de saída:

| Cenário | Chamadas/dia | Observação |
|---|---|---|
| 5 projetos estáveis | 0 a 5 | só erros esporádicos |
| 5 projetos, um com erro persistente | 5 a 50 | deduplicação limita a 2/h por padrão |
| 20 projetos, deploy diário | 20 a 100 | redeploy não dispara, erros pós-deploy sim |

Custo real depende do modelo escolhido. A tela de configuração mostra o preço por milhão de tokens
do modelo selecionado para que o usuário faça a conta.
