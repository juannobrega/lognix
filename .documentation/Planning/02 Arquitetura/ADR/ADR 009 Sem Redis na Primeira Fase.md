# ADR 009 — Sem Redis na Primeira Fase

**Status:** Aceito, condicionado a medição · **Data:** 2026-11-21

## Contexto

A rotina de análise roda a cada 30 s e há tarefas assíncronas: supervisão de túneis, chamadas de IA,
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
| Rotina de 30 s com 10 hosts e 100 containers termina em | menos de 20 s |
| Rotina de análise não bloqueia a API | p95 da API abaixo de 300 ms durante a rotina |
| Reinício do backend não perde tarefa de IA em andamento sem registro | 0 perdas silenciosas |
| Túneis de 10 hosts mantidos e reconectados sem afetar a rotina | sem falha em teste de 1 h |

## Alternativas consideradas

- **Celery + Redis desde o início.** Robusto e conhecido, mas pesado para a instalação e para o dev solo.
- **arq + Redis.** Mais leve que Celery, ainda exige Redis.
- **Postgres como fila.** Possível com `SKIP LOCKED`. Fica como opção intermediária se Redis for
  demais e o processo único for pouco.

## Consequências

- Compose inicial: backend, frontend, Postgres, Loki, Alloy. Cinco containers.
- O backend é instância única. Escalar horizontalmente exige revisitar este ADR.
- A medição vira item obrigatório do roadmap de construção, não opcional.
