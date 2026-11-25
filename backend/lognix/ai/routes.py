"""Rotas de insights, consumo de IA, teste de chave e lista de modelos."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, status
from pydantic import BaseModel
from sqlalchemy import Select, func, select, update

from lognix.ai.models import (
    AiCall,
    AiCallStatus,
    AiPurpose,
    CostSource,
    Insight,
    InsightStatus,
    Severity,
)
from lognix.ai.service import get_runtime
from lognix.analysis.models import TriggerFired, TriggerType
from lognix.auth.deps import CurrentUser, DbSession
from lognix.containers.models import Container
from lognix.errors import ApiError

insights_router = APIRouter(prefix="/insights", tags=["insights"])
settings_router = APIRouter(prefix="/settings", tags=["insights"])


class InsightOut(BaseModel):
    id: uuid.UUID
    container_id: uuid.UUID
    container_name: str | None = None
    host_name: str | None = None
    trigger_id: uuid.UUID
    trigger_type: TriggerType | None = None
    trigger_note: str | None = None
    severity: Severity
    title: str
    summary: str
    probable_cause: str
    suggested_action: str
    confidence: float
    needs_code: bool
    evidence: list[Any]
    code_diagnosis: dict[str, Any] | None
    context_truncated: bool
    status: InsightStatus
    seen_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InsightDetailOut(InsightOut):
    sent_context: str
    window_start: datetime | None = None
    window_end: datetime | None = None
    calls: list[AiCallOut] = []


class AiCallOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID | None = None
    provider: str = ""
    provider_name: str = ""
    attempt: int = 0
    fell_back: bool = False
    model: str
    purpose: AiPurpose
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    cost_source: CostSource
    latency_ms: int
    schema_retry: bool
    status: AiCallStatus
    error: str | None
    created_at: datetime
    container_name: str | None = None

    model_config = {"from_attributes": True}


class SeenAllOut(BaseModel):
    marked: int


class UsageBucket(BaseModel):
    key: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class ProviderUsage(BaseModel):
    provider_id: uuid.UUID | None
    name: str
    kind: str
    calls: int
    errors: int
    fallbacks: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    avg_latency_ms: int
    p95_latency_ms: int
    success_rate: float


class UsageOut(BaseModel):
    today: UsageBucket
    last_7d: UsageBucket
    last_30d: UsageBucket
    total: UsageBucket
    by_day: list[UsageBucket]
    by_project: list[UsageBucket]
    by_trigger: list[UsageBucket]
    by_purpose: list[UsageBucket]
    by_provider: list[ProviderUsage]
    by_model: list[UsageBucket]
    failures: int
    schema_retries: int
    fallbacks: int
    avg_latency_ms: int
    paused_providers: dict[str, datetime]


def _with_names(insight: Insight, container: Container, trigger: TriggerFired | None) -> InsightOut:
    out = InsightOut.model_validate(insight)
    out.container_name = container.name
    out.host_name = container.host.name
    if trigger is not None:
        out.trigger_type = trigger.type
        out.trigger_note = trigger.note
    return out


def _list_stmt(
    status_filter: InsightStatus | None,
) -> Select[Insight, Container, TriggerFired]:
    stmt: Select[Insight, Container, TriggerFired] = (
        select(Insight, Container, TriggerFired)
        .join(Container, Container.id == Insight.container_id)
        .join(TriggerFired, TriggerFired.id == Insight.trigger_id, isouter=True)
        .order_by(Insight.created_at.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(Insight.status == status_filter)
    return stmt


@insights_router.get("", response_model=list[InsightOut])
async def list_insights(
    _: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    severity: Annotated[Severity | None, Query()] = None,
) -> list[InsightOut]:
    stmt = _list_stmt(InsightStatus.new).limit(limit)
    if severity is not None:
        stmt = stmt.where(Insight.severity == severity)
    return [_with_names(i, c, t) for i, c, t in (await db.execute(stmt)).all()]


@insights_router.get("/history", response_model=list[InsightOut])
async def insights_history(
    _: CurrentUser, db: DbSession, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[InsightOut]:
    stmt = _list_stmt(InsightStatus.seen).limit(limit)
    return [_with_names(i, c, t) for i, c, t in (await db.execute(stmt)).all()]


@insights_router.post("/seen-all", response_model=SeenAllOut)
async def seen_all(user: CurrentUser, db: DbSession) -> SeenAllOut:
    result = await db.execute(
        update(Insight)
        .where(Insight.status == InsightStatus.new)
        .values(status=InsightStatus.seen, seen_by=user.id, seen_at=datetime.now(UTC))
    )
    await db.commit()
    return SeenAllOut(marked=int(getattr(result, "rowcount", 0) or 0))


@insights_router.get("/{insight_id}", response_model=InsightDetailOut)
async def get_insight(insight_id: uuid.UUID, _: CurrentUser, db: DbSession) -> InsightDetailOut:
    row = (
        await db.execute(
            select(Insight, Container, TriggerFired)
            .join(Container, Container.id == Insight.container_id)
            .join(TriggerFired, TriggerFired.id == Insight.trigger_id, isouter=True)
            .where(Insight.id == insight_id)
        )
    ).first()
    if row is None:
        raise ApiError(404, "not_found", "Insight não encontrado.")
    insight, container, trigger = row
    base = _with_names(insight, container, trigger)
    calls = (
        await db.execute(
            select(AiCall).where(AiCall.insight_id == insight.id).order_by(AiCall.created_at)
        )
    ).scalars()
    return InsightDetailOut(
        **base.model_dump(),
        sent_context=insight.sent_context,
        window_start=trigger.window_start if trigger else None,
        window_end=trigger.window_end if trigger else None,
        calls=[AiCallOut.model_validate(c) for c in calls],
    )


@insights_router.post("/{insight_id}/seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_seen(insight_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    insight = await db.get(Insight, insight_id)
    if insight is None:
        raise ApiError(404, "not_found", "Insight não encontrado.")
    insight.status = InsightStatus.seen
    insight.seen_by = user.id
    insight.seen_at = datetime.now(UTC)
    await db.commit()


# --- consumo -----------------------------------------------------------------


def _bucket(key: str, row: Any) -> UsageBucket:
    return UsageBucket(
        key=key,
        calls=int(row[0] or 0),
        input_tokens=int(row[1] or 0),
        output_tokens=int(row[2] or 0),
        cost_usd=Decimal(str(row[3] or 0)),
    )


_AGG = (
    func.count(),
    func.coalesce(func.sum(AiCall.input_tokens), 0),
    func.coalesce(func.sum(AiCall.output_tokens), 0),
    func.coalesce(func.sum(AiCall.cost_usd), 0),
)


@settings_router.get("/usage", response_model=UsageOut)
async def usage(_: CurrentUser, db: DbSession) -> UsageOut:
    now = datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async def window(since: datetime | None, key: str) -> UsageBucket:
        stmt = select(*_AGG)
        if since is not None:
            stmt = stmt.where(AiCall.created_at >= since)
        return _bucket(key, (await db.execute(stmt)).one())

    by_day_rows = (
        await db.execute(
            select(func.date_trunc("day", AiCall.created_at).label("d"), *_AGG)
            .where(AiCall.created_at >= now - timedelta(days=30))
            .group_by("d")
            .order_by("d")
        )
    ).all()
    by_project_rows = (
        await db.execute(
            select(Container.name, *_AGG)
            .join(Container, Container.id == AiCall.container_id)
            .group_by(Container.name)
            .order_by(func.coalesce(func.sum(AiCall.cost_usd), 0).desc())
            .limit(20)
        )
    ).all()
    by_trigger_rows = (
        await db.execute(
            select(TriggerFired.type, *_AGG)
            .join(TriggerFired, TriggerFired.id == AiCall.trigger_id)
            .group_by(TriggerFired.type)
        )
    ).all()
    by_purpose_rows = (
        await db.execute(select(AiCall.purpose, *_AGG).group_by(AiCall.purpose))
    ).all()
    by_model_rows = (
        await db.execute(
            select(AiCall.model, *_AGG)
            .group_by(AiCall.model)
            .order_by(func.coalesce(func.sum(AiCall.cost_usd), 0).desc())
            .limit(20)
        )
    ).all()
    provider_rows = (
        await db.execute(
            select(
                AiCall.provider_id,
                func.max(AiCall.provider_name),
                func.max(AiCall.provider),
                func.count(),
                func.count().filter(AiCall.status == AiCallStatus.error),
                func.count().filter(AiCall.fell_back.is_(True)),
                func.coalesce(func.sum(AiCall.input_tokens), 0),
                func.coalesce(func.sum(AiCall.output_tokens), 0),
                func.coalesce(func.sum(AiCall.cost_usd), 0),
                func.coalesce(func.avg(AiCall.latency_ms), 0),
                func.coalesce(func.percentile_cont(0.95).within_group(AiCall.latency_ms.asc()), 0),
            )
            .group_by(AiCall.provider_id)
            .order_by(func.count().desc())
        )
    ).all()
    failures = int(
        (
            await db.execute(
                select(func.count()).select_from(AiCall).where(AiCall.status == AiCallStatus.error)
            )
        ).scalar_one()
    )
    retries = int(
        (
            await db.execute(
                select(func.count()).select_from(AiCall).where(AiCall.schema_retry.is_(True))
            )
        ).scalar_one()
    )
    return UsageOut(
        today=await window(today, "hoje"),
        last_7d=await window(now - timedelta(days=7), "7 dias"),
        last_30d=await window(now - timedelta(days=30), "30 dias"),
        total=await window(None, "total"),
        by_day=[_bucket(r[0].date().isoformat(), r[1:]) for r in by_day_rows],
        by_project=[_bucket(str(r[0]), r[1:]) for r in by_project_rows],
        by_trigger=[_bucket(str(r[0].value), r[1:]) for r in by_trigger_rows],
        by_purpose=[_bucket(str(r[0].value), r[1:]) for r in by_purpose_rows],
        by_model=[_bucket(str(r[0]), r[1:]) for r in by_model_rows],
        by_provider=[
            ProviderUsage(
                provider_id=r[0],
                name=str(r[1] or "removido"),
                kind=str(r[2] or ""),
                calls=int(r[3] or 0),
                errors=int(r[4] or 0),
                fallbacks=int(r[5] or 0),
                input_tokens=int(r[6] or 0),
                output_tokens=int(r[7] or 0),
                cost_usd=Decimal(str(r[8] or 0)),
                avg_latency_ms=int(r[9] or 0),
                p95_latency_ms=int(r[10] or 0),
                success_rate=round(1 - (int(r[4] or 0) / max(int(r[3] or 1), 1)), 4),
            )
            for r in provider_rows
        ],
        failures=failures,
        schema_retries=retries,
        fallbacks=int(
            (
                await db.execute(
                    select(func.count()).select_from(AiCall).where(AiCall.fell_back.is_(True))
                )
            ).scalar_one()
        ),
        avg_latency_ms=int(
            (await db.execute(select(func.coalesce(func.avg(AiCall.latency_ms), 0)))).scalar_one()
        ),
        paused_providers=get_runtime().paused_all(),
    )


@settings_router.get("/usage/calls", response_model=list[AiCallOut])
async def usage_calls(
    _: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    only: Annotated[Literal["all", "errors"], Query()] = "all",
) -> list[AiCallOut]:
    stmt = (
        select(AiCall, Container.name)
        .join(Container, Container.id == AiCall.container_id, isouter=True)
        .order_by(AiCall.created_at.desc())
        .limit(limit)
    )
    if only == "errors":
        stmt = stmt.where(AiCall.status == AiCallStatus.error)
    out = []
    for call, name in (await db.execute(stmt)).all():
        item = AiCallOut.model_validate(call)
        item.container_name = name
        out.append(item)
    return out
