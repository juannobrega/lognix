"""Métricas Prometheus do próprio Lognix. Planning > Observabilidade do Lognix.

Expostas em GET /api/v1/metrics, só alcançável na rede interna do compose.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

# --- ciclo de análise --------------------------------------------------------
cycle_duration = Histogram(
    "lognix_cycle_duration_seconds",
    "Duração de uma fase do ciclo de análise",
    ["phase"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
cycles_total = Counter("lognix_cycles_total", "Ciclos de análise concluídos", ["status"])
cycle_lines = Histogram(
    "lognix_cycle_lines",
    "Linhas processadas por ciclo",
    buckets=(0, 1, 10, 100, 1000, 5000, 20000, 50000),
)
triggers_total = Counter("lognix_triggers_total", "Triggers disparados", ["type"])
analysis_loops = Gauge("lognix_analysis_loops", "Loops de análise ativos")

# --- IA (fase 0.9.0, já declarado para a tela de consumo) --------------------
ai_calls_total = Counter("lognix_ai_calls_total", "Chamadas de IA", ["status", "purpose"])
ai_semaphore_waiting = Gauge("lognix_ai_semaphore_waiting", "Chamadas de IA aguardando vaga")

# --- túneis e hosts ----------------------------------------------------------
tunnels = Gauge("lognix_tunnels", "Túneis por estado", ["state"])
tunnel_reconnects_total = Counter("lognix_tunnel_reconnects_total", "Reconexões de túnel")
events_stream_restarts_total = Counter(
    "lognix_events_stream_restarts_total", "Reaberturas do stream de eventos Docker"
)
docker_proxy_requests_total = Counter(
    "lognix_docker_proxy_requests_total", "Requisições à Docker API pelo proxy", ["outcome"]
)
docker_events_total = Counter("lognix_docker_events_total", "Eventos Docker recebidos", ["type"])
inventory_sync_duration = Histogram(
    "lognix_inventory_sync_duration_seconds",
    "Duração da reconciliação de inventário",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# --- Loki --------------------------------------------------------------------
loki_query_duration = Histogram(
    "lognix_loki_query_duration_seconds",
    "Duração de uma consulta ao Loki",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
loki_queries_total = Counter("lognix_loki_queries_total", "Consultas ao Loki", ["status"])
loki_tails = Gauge("lognix_loki_tails", "Tails abertos no Loki")

# --- API ---------------------------------------------------------------------
http_request_duration = Histogram(
    "http_request_duration_seconds",
    "Duração das requisições HTTP",
    ["route", "method", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
http_requests_in_flight = Gauge("http_requests_in_flight", "Requisições HTTP em andamento")


async def metrics_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.url.path.endswith("/metrics"):
        return await call_next(request)
    start = time.perf_counter()
    http_requests_in_flight.inc()
    status = "500"
    try:
        response = await call_next(request)
        status = str(response.status_code)
        return response
    finally:
        http_requests_in_flight.dec()
        route = request.scope.get("route")
        # Rota do template (/projects/{id}/logs), não o caminho concreto: evita explosão de séries.
        path = getattr(route, "path", None) or "unmatched"
        http_request_duration.labels(path, request.method, status).observe(
            time.perf_counter() - start
        )


def render() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
