# Workers e Tarefas

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Tudo em um processo, ADR 009. Este documento define como os loops convivem e falham com segurança.

## 1. Inventário de loops

| Loop | Instâncias | Disparo | Duração típica | Pode falhar sem derrubar outros |
|---|---|---|---|---|
| Ciclo de análise | 1 por container monitorado | 30 s após o fim do anterior | 1 a 5 s sem IA, até 60 s com IA | sim |
| Supervisor de túnel | 1 por host | a cada 15 s | ms | sim |
| Ouvinte de eventos | 1 por host | stream contínuo | — | sim, reabre com `since` |
| Reconciliação de inventário | 1 por host | 60 s | < 1 s | sim |
| Tail de logs | 1 por projeto com espectadores | enquanto houver cliente | — | sim |
| Periódicos | 1 global | APScheduler | — | sim |

## 2. Gerenciador de loops

Um componente `LoopManager` no startup:

- Cria e cancela loops conforme hosts e containers mudam. Marcar container como monitorado cria seu
  ciclo; desmarcar cancela.
- Cada loop roda em `try/except` com registro de erro e reinício após backoff. Erro repetido 5 vezes
  em 5 minutos gera notificação e pausa o loop por 5 minutos.
- Expõe estado em `GET /health/loops`: nome, instância, último início, último fim, último erro,
  contagem de falhas.
- No shutdown, cancela tudo e espera até 10 s pela conclusão de chamadas de IA em andamento. Chamada
  interrompida vira `AICall.status = error` com motivo `shutdown`.

## 3. Ciclo de análise, detalhe

```
loop:
  window_start = last_window_end or monitored_since
  window_end   = now()
  lines        = loki.query(container, window_start, window_end)
  run          = AnalysisRun(window_start, window_end, ...)
  patterns.update(lines); classify(lines); stats.update(run)
  fired        = triggers.evaluate(run, lines, events)
  if fired and ai.enabled:
      async with ai_semaphore:            # concorrência global, padrão 3
          insight = ai.analyze(context)   # inclui retry de esquema
  elif fired:
      record TriggerFired without insight
  last_window_end = window_end
  sleep(30)
```

Se a consulta ao Loki falhar, o ciclo registra `AnalysisRun.status = failed`, **não avança**
`last_window_end`, e tenta de novo após 30 s. Nenhuma linha é pulada por falha transitória.

## 4. Periódicos

| Tarefa | Frequência | Faz |
|---|---|---|
| Retenção de eventos | diária | apaga `DockerEvent` e `HostEvent` além de 15 dias |
| Retenção de `AnalysisRun` | diária | além de 7 dias |
| Poda de `AlloyConfigVersion` | diária | mantém 100 |
| Cache de modelos e preços | a cada 24 h | OpenRouter |
| Limpeza de refresh tokens expirados | diária | |

## 5. Medição, ADR 009

Métricas internas expostas em `/metrics` no formato Prometheus, para a fase 0.7.0: duração de ciclo
por fase, fila do semáforo de IA, latência da API, túneis conectados, reconexões. Se os critérios do
ADR 009 falharem, a migração para fila externa troca o `LoopManager` por workers, sem mudar os domínios.
