# ADR 009 — Sem Redis na Primeira Fase

**Status:** Aceito, condicionado a medição; aprovado para construção em 2026-11-22 · **Data:** 2026-11-21

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

## Alternativas consideradas

- **Celery + Redis desde o início.** Robusto e conhecido, mas pesado para a instalação e para o dev solo.
- **arq + Redis.** Mais leve que Celery, ainda exige Redis.
- **Postgres como fila.** Possível com `SKIP LOCKED`. Fica como opção intermediária se Redis for
  demais e o processo único for pouco.

## Consequências

- Compose inicial: backend, frontend, Postgres, Loki, Alloy. Cinco containers.
- O backend é instância única. Escalar horizontalmente exige revisitar este ADR.
- A medição vira item obrigatório do roadmap de construção, não opcional.
