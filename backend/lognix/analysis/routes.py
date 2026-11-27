"""Rotas: padrões, ciclos, análise manual, triggers sem análise, executor."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from lognix.analysis import manual
from lognix.analysis.cycle import cycle_lock, run_cycle
from lognix.analysis.executor import get_executor
from lognix.analysis.manager import get_analysis_manager
from lognix.analysis.models import (
    AnalysisRun,
    LogLevel,
    Pattern,
    RunStatus,
    TriggerFired,
    TriggerType,
)
from lognix.auth.deps import CurrentUser, DbSession
from lognix.containers.models import Container
from lognix.errors import ApiError
from lognix.hosts.models import HostStatus
from lognix.loki.client import LokiClient

projects_router = APIRouter(prefix="/projects", tags=["analysis"])
insights_router = APIRouter(prefix="/insights", tags=["analysis"])
executor_router = APIRouter(prefix="/executor", tags=["analysis"])


class PatternOut(BaseModel):
    id: uuid.UUID
    template: str
    level: LogLevel
    count_total: int
    sample: str
    ignored: bool
    first_seen_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: int
    window_start: datetime
    window_end: datetime
    lines_count: int
    error_lines_count: int
    warn_lines_count: int
    new_patterns_count: int
    duration_ms: int
    truncated: bool
    manual: bool
    status: RunStatus
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TriggerOut(BaseModel):
    id: uuid.UUID
    analysis_run_id: int | None
    container_id: uuid.UUID
    type: TriggerType
    reason: dict[str, Any]
    fired_at: datetime
    window_start: datetime
    window_end: datetime
    sample_lines: list[Any]
    note: str | None
    insight_id: uuid.UUID | None
    container_name: str | None = None
    host_name: str | None = None

    model_config = {"from_attributes": True}


class AnalyzeIn(BaseModel):
    start: datetime | None = None
    end: datetime | None = None
    minutes: int = Field(default=15, ge=1, le=24 * 60)


class AnalyzeOut(BaseModel):
    run: RunOut
    triggers: list[TriggerOut]


class PatternIgnoreIn(BaseModel):
    ignored: bool


async def _project(db: DbSession, project_id: uuid.UUID) -> Container:
    c = await db.get(Container, project_id)
    if c is None or c.host.status == HostStatus.removed:
        raise ApiError(404, "not_found", "Projeto não encontrado.")
    return c


@projects_router.get("/{project_id}/patterns", response_model=list[PatternOut])
async def patterns(project_id: uuid.UUID, _: CurrentUser, db: DbSession) -> list[PatternOut]:
    await _project(db, project_id)
    rows = (
        await db.execute(
            select(Pattern)
            .where(Pattern.container_id == project_id)
            .order_by(Pattern.count_total.desc())
        )
    ).scalars()
    return [PatternOut.model_validate(p) for p in rows]


@projects_router.put("/{project_id}/patterns/{pattern_id}/ignore", response_model=PatternOut)
async def ignore_pattern(
    project_id: uuid.UUID,
    pattern_id: uuid.UUID,
    body: PatternIgnoreIn,
    _: CurrentUser,
    db: DbSession,
) -> PatternOut:
    await _project(db, project_id)
    p = await db.get(Pattern, pattern_id)
    if p is None or p.container_id != project_id:
        raise ApiError(404, "not_found", "Padrão não encontrado.")
    p.ignored = body.ignored
    await db.commit()
    await db.refresh(p)
    return PatternOut.model_validate(p)


@projects_router.get("/{project_id}/analysis-runs", response_model=list[RunOut])
async def runs(
    project_id: uuid.UUID,
    _: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[RunOut]:
    await _project(db, project_id)
    rows = (
        await db.execute(
            select(AnalysisRun)
            .where(AnalysisRun.container_id == project_id)
            .order_by(AnalysisRun.id.desc())
            .limit(limit)
        )
    ).scalars()
    return [RunOut.model_validate(r) for r in rows]


@projects_router.get("/{project_id}/triggers", response_model=list[TriggerOut])
async def project_triggers(
    project_id: uuid.UUID, _: CurrentUser, db: DbSession
) -> list[TriggerOut]:
    await _project(db, project_id)
    rows = (
        await db.execute(
            select(TriggerFired)
            .where(TriggerFired.container_id == project_id)
            .order_by(TriggerFired.fired_at.desc())
            .limit(200)
        )
    ).scalars()
    return [TriggerOut.model_validate(t) for t in rows]


@projects_router.post(
    "/{project_id}/analyze", response_model=AnalyzeOut, status_code=status.HTTP_201_CREATED
)
async def analyze_now(
    project_id: uuid.UUID, body: AnalyzeIn, user: CurrentUser, db: DbSession
) -> AnalyzeOut:
    container = await _project(db, project_id)
    if manual.espera(project_id) > 0:
        raise ApiError(
            429,
            "rate_limited",
            "Análise manual limitada a uma por minuto por projeto.",
            "Aguarde um minuto.",
        )
    manual.marcar(project_id)
    end = body.end or datetime.now(UTC)
    start = body.start or (end - timedelta(minutes=body.minutes))
    if start >= end:
        raise ApiError(400, "bad_range", "start precisa ser anterior a end.")
    key = get_executor().start(container.id, container.name, container.host.name, "manual")
    client = LokiClient()
    try:
        # Espera o ciclo automático terminar, se estiver no meio de um.
        async with cycle_lock(container.id):
            result = await run_cycle(
                db,
                client,
                container,
                window_start=start,
                window_end=end,
                manual=True,
                fired_by=user.id,
                on_phase=lambda p, **d: get_executor().phase(key, p, **d),
            )
    finally:
        await client.aclose()
        get_executor().finish(key)
    if result.run.status == RunStatus.failed:
        raise ApiError(502, "loki_error", result.run.error or "Falha ao consultar o Loki.")
    return AnalyzeOut(
        run=RunOut.model_validate(result.run),
        triggers=[TriggerOut.model_validate(t) for t in result.fired],
    )


@insights_router.get("/unanalyzed", response_model=list[TriggerOut])
async def unanalyzed(
    _: CurrentUser, db: DbSession, limit: Annotated[int, Query(ge=1, le=500)] = 200
) -> list[TriggerOut]:
    rows = (
        await db.execute(
            select(TriggerFired, Container)
            .join(Container, Container.id == TriggerFired.container_id)
            .where(TriggerFired.insight_id.is_(None))
            .order_by(TriggerFired.fired_at.desc())
            .limit(limit)
        )
    ).all()
    out = []
    for t, c in rows:
        item = TriggerOut.model_validate(t)
        item.container_name = c.name
        item.host_name = c.host.name
        out.append(item)
    return out


@executor_router.get("", response_model=dict[str, Any])
async def executor_state(_: CurrentUser) -> dict[str, Any]:
    return {"running": get_executor().snapshot(), "loops": get_analysis_manager().status()}
