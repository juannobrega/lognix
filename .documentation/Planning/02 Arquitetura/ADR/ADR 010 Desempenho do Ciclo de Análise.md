# ADR 010 — Desempenho do Ciclo de Análise

**Status:** Aceito · **Data:** 2026-11-24

## Contexto

A medição do [ADR 009](ADR%20009%20Sem%20Redis%20na%20Primeira%20Fase.md) reprovou o critério de latência
da API: com 100 containers em ciclo, o p95 foi a **1691 ms**, quase seis vezes o limite de 300 ms.

A hipótese do ADR 009 era que faltaria uma fila externa. A medição mostrou outra coisa. A parte
determinística do ciclo (Drain, regex de classificação, montagem de padrões) é **trabalho de CPU em
Python puro**. Num processo asyncio, um laço de CPU sem `await` **não cede o event loop**: enquanto
um ciclo processa milhares de linhas, nenhuma requisição HTTP é atendida. Uma fila externa não
resolveria isso; só moveria o mesmo laço para outro processo, pagando serialização e operação.

## Decisão

Três mudanças, nenhuma delas uma fila:

1. **Ceder o loop durante o trabalho de CPU.** O laço que classifica e minera linhas faz
   `await asyncio.sleep(0)` a cada 250 linhas (`YIELD_EVERY` em `analysis/cycle.py`). O custo é
   desprezível e a API volta a ser atendida entre blocos.
2. **Limitar ciclos simultâneos.** `AnalysisManager` tem um semáforo, padrão 8
   (`LOGNIX_ANALYSIS_CONCURRENCY`). Rodar 100 ciclos ao mesmo tempo não acelera nada: o trabalho é
   CPU e banco. Só aumenta a latência de todo mundo.
3. **Dimensionar o pool do banco.** O padrão do SQLAlchemy, 5 conexões mais 10 de overflow, é pequeno
   para muitos ciclos simultâneos: os ciclos consomem o pool e a API fica na fila. Agora 20 mais 10
   (`LOGNIX_DB_POOL_SIZE`, `LOGNIX_DB_MAX_OVERFLOW`).

## Resultado

| Cenário | Antes | Depois |
|---|---|---|
| p95 da API em saturação, ciclos sem pausa | 1691 ms | **118 ms** |
| p95 da API no regime real | não medido | **42 ms** |
| p95 do ciclo determinístico | 431 ms | 948 ms |

O ciclo individual ficou um pouco mais lento, efeito esperado de dividir a CPU entre mais trabalho
concorrente. O que importa, a responsividade da interface, melhorou catorze vezes.

## Alternativas consideradas

- **Fila externa com Redis.** O que o ADR 009 previa. Não atacaria a causa, e acrescentaria um
  container e uma peça de operação. Rejeitada pela medição.
- **Mover o ciclo para `asyncio.to_thread`.** O GIL limita o ganho em Python puro, e o código de
  banco é async: exigiria duas pontes. Guardada caso o Drain vire gargalo real.
- **Processos separados.** Mesma objeção da fila, com mais complexidade.

## Consequências

- A concorrência de ciclos é um botão explícito, visível e documentado.
- `YIELD_EVERY` é um número arbitrário escolhido por medição. Mudá-lo exige remedir.
- O harness `backend/scripts/measure.py` fica no repositório: toda mudança no ciclo pode ser medida
  contra a mesma régua.
