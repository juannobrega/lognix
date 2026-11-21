# Observabilidade do Lognix

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Como o Lognix monitora a si mesmo. Sem isso, a fase 0.7.0 não consegue medir o ADR 009.

## 1. Logs do próprio Lognix

- Backend em JSON estruturado para stdout, com `level`, `logger`, `host_id`, `container_id`,
  `loop`, quando aplicável.
- Nunca logar credenciais, tokens, conteúdo de linhas de log de hosts nem contexto enviado à IA.
  Esses ficam no banco com acesso controlado, não no stdout.
- O Alloy pode, opcionalmente, coletar os logs do próprio compose para o mesmo Loki, com label
  `host="lognix"`. Desligado por padrão para não confundir o usuário.

## 2. Métricas

`GET /metrics` no backend, formato Prometheus, só na rede interna:

| Métrica | Tipo | Uso |
|---|---|---|
| `lognix_cycle_duration_seconds{phase}` | histograma | fases: loki, drain, classify, triggers, ai |
| `lognix_cycles_total{status}` | contador | ok, failed, truncated |
| `lognix_ai_calls_total{status,purpose}` | contador | |
| `lognix_ai_semaphore_waiting` | gauge | fila por concorrência |
| `lognix_tunnels{state}` | gauge | connected, disconnected, error |
| `lognox_tunnel_reconnects_total` | contador | |
| `lognix_events_stream_restarts_total` | contador | |
| `lognix_loki_query_duration_seconds` | histograma | |
| `http_request_duration_seconds{route,status}` | histograma | p95 da API, ADR 009 |

Na fase 0.7.0, um compose de medição adiciona Prometheus e Grafana para ler essas métricas. Não faz
parte da instalação padrão.

## 3. Tela Sistema

A interface expõe o essencial sem Prometheus: estado de Postgres, Loki, Alloy; loops com último erro;
túneis; uso de disco dos volumes quando disponível; versão. Rota `/settings/system`.

## 4. Alertas internos

Viram notificações na própria interface, não há canal externo na v1:

- Loop pausado por falhas repetidas.
- Reload do Alloy falhou.
- Volume excessivo em um container.
- Disco do Loki acima de 85 %, se mensurável.
