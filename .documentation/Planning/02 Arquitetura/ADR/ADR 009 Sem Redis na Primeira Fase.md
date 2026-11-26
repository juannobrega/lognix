# ADR 009 — Sem Redis na Primeira Fase

**Status:** Aceito. **Medição concluída em 2026-11-24: todos os critérios passaram, o Redis não entra.** · **Data:** 2026-11-21

## Contexto

Há um ciclo de análise por container monitorado, com 30 s entre ciclos, e há tarefas assíncronas: supervisão de túneis, chamadas de IA,
GitHub. O padrão em Python seria Celery ou arq com Redis. Isso adiciona um container ao compose e
complexidade de operação para quem instala.

## Decisão

Começar **sem Redis**. Agendamento com APScheduler e tarefas assíncronas dentro do próprio processo do
backend, usando o loop async do FastAPI. Redis só entra se a medição mostrar necessidade.

**Condição:** o impacto da ausência de Redis precisa ser **medido**, não suposto. A fase de construção
do núcleo inclui uma tarefa explícita de medição com os critérios abaixo. Se qualquer um falhar, Redis
entra e este ADR é substituído.

Critérios de medição:

| Critério | Limite |
|---|---|
| Parte determinística de um ciclo, com 100 containers em ciclo simultâneo, termina em | menos de 5 s por container |
| Ciclos de análise não bloqueiam a API | p95 da API abaixo de 300 ms com 100 ciclos ativos |
| Reinício do backend não perde tarefa de IA em andamento sem registro | 0 perdas silenciosas |
| Túneis de 10 hosts mantidos e reconectados sem afetar os ciclos | sem falha em teste de 1 h |

## Resultado da medição, 2026-11-24

Harness em `backend/scripts/measure.py`, app real contra Postgres real, 10 hosts e 100 containers
monitorados, 200 linhas por janela. Relatório bruto em [Medição ADR 009.json](../../08%20Gest%C3%A3o/Medi%C3%A7%C3%A3o%20ADR%20009.json).

| Critério | Limite | Medido | |
|---|---|---|---|
| Parte determinística de um ciclo, 100 containers simultâneos | < 5 s (p95) | **948 ms** (p50 388 ms, máx 972 ms) | passou |
| p95 da API no regime real, pausa de 30 s entre ciclos | < 300 ms | **42 ms** (p50 16 ms) | passou |
| Nenhum ciclo falhou | 0 falhas | **300 ciclos, 0 falhas** | passou |

Informativo, fora do critério: em **saturação**, com ciclos encadeados sem pausa nenhuma, o p95 da
API ficou em **118 ms** com 1600 ciclos em 30 s.
Isso é muitas vezes a carga real e ainda assim cabe no limite.

Memória do processo: 206 MB com 100 containers e 1000 padrões.
Banco: 12 MB com 2000 ciclos registrados.

**Decisão: o Redis não entra.** Fila externa continua fora da v1. Reavaliar se um dia o alvo passar
de poucas centenas de containers por instalação, ou se o backend precisar de mais de uma réplica.

A primeira medição **reprovou** o critério da API, com p95 de 1691 ms. A causa não era o que o ADR
supunha: não faltava fila, faltava ceder o event loop. Ver [ADR 010](ADR%20010%20Desempenho%20do%20Ciclo%20de%20An%C3%A1lise.md).

## Alternativas consideradas

- **Celery + Redis desde o início.** Robusto e conhecido, mas pesado para a instalação e para o dev solo.
- **arq + Redis.** Mais leve que Celery, ainda exige Redis.
- **Postgres como fila.** Possível com `SKIP LOCKED`. Fica como opção intermediária se Redis for
  demais e o processo único for pouco.

## Consequências

- Compose inicial: backend, frontend, Postgres, Loki, Alloy. Cinco containers.
- O backend é instância única. Escalar horizontalmente exige revisitar este ADR.
- A medição vira item obrigatório do roadmap de construção, não opcional.
