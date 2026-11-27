"""Métricas Prometheus e estado do sistema para a tela Sistema."""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select
from starlette.responses import Response

from lognix import __version__
from lognix.analysis.manager import get_analysis_manager
from lognix.analysis.models import AnalysisRun, Pattern, TriggerFired
from lognix.api.health import check_http, check_postgres
from lognix.auth.deps import CurrentUser, DbSession
from lognix.config import get_settings
from lognix.containers.models import Container, ContainerState
from lognix.events.workers import get_host_workers
from lognix.hosts.models import Host, HostStatus
from lognix.hosts.supervisor import get_supervisor
from lognix.metrics import render
from lognix.realtime.hub import get_tail_hub

router = APIRouter(tags=["system"])


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Formato Prometheus. Só alcançável na rede interna do compose."""
    get_supervisor().refresh_gauges()
    return render()


class ComponentOut(BaseModel):
    ok: bool
    detail: str | None = None


class LoopOut(BaseModel):
    kind: str
    count: int
    detail: list[dict[str, Any]] = []


class VolumeOut(BaseModel):
    path: str
    total_bytes: int | None
    used_bytes: int | None
    free_bytes: int | None


class ConfigFileOut(BaseModel):
    """Onde o Lognix procurou o config.yaml, e o que achou lá."""

    path: str
    found: bool
    keys: list[str]
    providers: int


class SystemOut(BaseModel):
    version: str
    started_at: datetime
    uptime_seconds: int
    retention_days: int
    analysis_interval_seconds: int
    components: dict[str, ComponentOut]
    counts: dict[str, int]
    loops: list[LoopOut]
    volumes: list[VolumeOut]
    proxy_rejected_total: int
    config_file: ConfigFileOut


_started_at = datetime.now(UTC)


def _volume(path: str) -> VolumeOut:
    try:
        usage = shutil.disk_usage(path)
        return VolumeOut(
            path=path, total_bytes=usage.total, used_bytes=usage.used, free_bytes=usage.free
        )
    except OSError:
        return VolumeOut(path=path, total_bytes=None, used_bytes=None, free_bytes=None)


@router.get("/system", response_model=SystemOut)
async def system(_: CurrentUser, db: DbSession) -> SystemOut:
    from lognix.settings import config_file

    settings = get_settings()
    arquivo = config_file.active()
    postgres = await check_postgres()
    loki = await check_http(f"{settings.loki_url}/ready")
    alloy = await check_http(f"{settings.alloy_url}/-/ready")

    async def count(model: Any, *where: Any) -> int:
        stmt = select(func.count()).select_from(model)
        for clause in where:
            stmt = stmt.where(clause)
        return int((await db.execute(stmt)).scalar_one())

    supervisor = get_supervisor()
    workers = get_host_workers()
    hosts = list(
        (await db.execute(select(Host).where(Host.status != HostStatus.removed))).scalars()
    )
    counts = {
        "hosts": len(hosts),
        "hosts_connected": sum(1 for h in hosts if h.status == HostStatus.connected),
        "containers": await count(Container, Container.state != ContainerState.removed),
        "monitored": await count(
            Container, Container.monitored.is_(True), Container.state != ContainerState.removed
        ),
        "excluded": await count(Container, Container.state == ContainerState.removed),
        "patterns": await count(Pattern),
        "analysis_runs": await count(AnalysisRun),
        "triggers": await count(TriggerFired),
        "triggers_unanalyzed": await count(TriggerFired, TriggerFired.insight_id.is_(None)),
    }
    tunnel_detail = []
    rejected = 0
    for host in hosts:
        runner = supervisor.get(host.id)
        worker = workers.get(host.id)
        proxy = getattr(getattr(runner, "tunnel", None), "_proxy", None)
        rejected += getattr(proxy, "rejected_count", 0) or 0
        tunnel_detail.append(
            {
                "host": host.name,
                "status": host.status.value,
                "connected": bool(runner and runner.tunnel.connected),
                "reconnect_attempts": runner.attempts if runner else 0,
                "events_seen": worker.events_seen if worker else 0,
                "stream_restarts": worker.stream_restarts if worker else 0,
                "last_error": (runner.last_error if runner else None) or host.last_error,
            }
        )
    loops = [
        LoopOut(kind="tunnels", count=len(tunnel_detail), detail=tunnel_detail),
        LoopOut(
            kind="analysis",
            count=len(get_analysis_manager().status()),
            detail=get_analysis_manager().status(),
        ),
        LoopOut(kind="log_tails", count=len(get_tail_hub().active_projects())),
    ]
    now = datetime.now(UTC)
    return SystemOut(
        version=__version__,
        started_at=_started_at,
        uptime_seconds=int((now - _started_at).total_seconds()),
        retention_days=settings.loki_retention_days,
        analysis_interval_seconds=30,
        components={
            "postgres": ComponentOut(**postgres.model_dump()),
            "loki": ComponentOut(**loki.model_dump()),
            "alloy": ComponentOut(**alloy.model_dump()),
        },
        counts=counts,
        loops=loops,
        volumes=[
            _volume(settings.tunnels_dir),
            _volume(os.path.dirname(settings.alloy_config_path) or "/"),
        ],
        proxy_rejected_total=rejected,
        config_file=ConfigFileOut(
            path=str(arquivo.path or settings.config_file),
            found=bool(arquivo.managed or arquivo.providers),
            keys=sorted(arquivo.managed),
            providers=len(arquivo.providers),
        ),
    )
