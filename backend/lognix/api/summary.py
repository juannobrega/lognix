"""Resumo do painel: tudo que a tela inicial precisa numa chamada só."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from lognix.analysis.models import AnalysisRun, RunStatus, TriggerFired
from lognix.auth.deps import CurrentUser, DbSession
from lognix.containers.models import Container, ContainerState
from lognix.hosts.models import Host, HostStatus
from lognix.notifications.models import Notification, NotificationStatus

router = APIRouter(prefix="/summary", tags=["summary"])


class HostSummary(BaseModel):
    id: uuid.UUID
    name: str
    status: HostStatus
    monitored: int
    last_error: str | None


class ProjectActivity(BaseModel):
    id: uuid.UUID
    name: str
    host_name: str
    state: ContainerState
    lines_24h: int
    errors_24h: int
    triggers_24h: int


class PontoHora(BaseModel):
    """Uma hora da série. `hour` é o começo da hora, em UTC."""

    hour: datetime
    lines: int
    errors: int


class Fatia(BaseModel):
    key: str
    count: int


class PontoDia(BaseModel):
    day: str
    cost_usd: Decimal
    calls: int


class SummaryOut(BaseModel):
    hosts_total: int
    hosts_connected: int
    projects_total: int
    projects_with_errors_1h: int
    notifications_new: int
    triggers_new_24h: int
    triggers_unanalyzed: int
    lines_24h: int
    errors_24h: int
    cycles_24h: int
    cycles_failed_24h: int
    ai_enabled: bool
    hosts: list[HostSummary]
    top_projects: list[ProjectActivity]
    #: Séries para os gráficos. Um número sozinho diz o tamanho; a série diz a direção, que é
    #: a pergunta que alguém faz ao abrir um painel.
    lines_by_hour: list[PontoHora]
    triggers_by_type: list[Fatia]
    insights_by_severity: list[Fatia]
    cost_by_day: list[PontoDia]


async def _series(
    db: DbSession, day_ago: datetime
) -> dict[str, list[PontoHora] | list[Fatia] | list[PontoDia]]:
    """As quatro séries dos gráficos, em quatro consultas agregadas.

    Agregar no banco e não em Python: trazer 24 horas de ciclos para somar na aplicação seria
    mover milhares de linhas pela rede para produzir 24 números.
    """
    from lognix.ai.models import AiCall, Insight, InsightStatus

    hora = func.date_trunc("hour", AnalysisRun.window_end)
    por_hora = (
        await db.execute(
            select(
                hora.label("hour"),
                func.coalesce(func.sum(AnalysisRun.lines_count), 0),
                func.coalesce(func.sum(AnalysisRun.error_lines_count), 0),
            )
            .where(AnalysisRun.window_end >= day_ago)
            .group_by(hora)
            .order_by(hora)
        )
    ).all()

    por_tipo = (
        await db.execute(
            select(TriggerFired.type, func.count())
            .where(TriggerFired.fired_at >= day_ago)
            .group_by(TriggerFired.type)
            .order_by(func.count().desc())
        )
    ).all()

    # Só os insights ainda não vistos: o painel mostra o que está em aberto, não o histórico.
    por_severidade = (
        await db.execute(
            select(Insight.severity, func.count())
            .where(Insight.status == InsightStatus.new)
            .group_by(Insight.severity)
        )
    ).all()

    dia = func.date_trunc("day", AiCall.created_at)
    por_dia = (
        await db.execute(
            select(dia.label("day"), func.coalesce(func.sum(AiCall.cost_usd), 0), func.count())
            .where(AiCall.created_at >= day_ago - timedelta(days=6))
            .group_by(dia)
            .order_by(dia)
        )
    ).all()

    return {
        "lines_by_hour": [
            PontoHora(hour=h, lines=int(linhas or 0), errors=int(erros or 0))
            for h, linhas, erros in por_hora
        ],
        "triggers_by_type": [Fatia(key=str(t.value), count=int(n)) for t, n in por_tipo],
        "insights_by_severity": [
            Fatia(key=str(sev.value), count=int(n)) for sev, n in por_severidade
        ],
        "cost_by_day": [
            PontoDia(day=d.date().isoformat(), cost_usd=Decimal(custo or 0), calls=int(n))
            for d, custo, n in por_dia
        ],
    }


@router.get("", response_model=SummaryOut)
async def summary(_: CurrentUser, db: DbSession) -> SummaryOut:
    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)
    hour_ago = now - timedelta(hours=1)

    hosts = list(
        (
            await db.execute(
                select(Host).where(Host.status != HostStatus.removed).order_by(Host.name)
            )
        ).scalars()
    )
    monitored_by_host = dict(
        (
            await db.execute(
                select(Container.host_id, func.count())
                .where(Container.monitored.is_(True), Container.state != ContainerState.removed)
                .group_by(Container.host_id)
            )
        ).all()
    )

    async def scalar(stmt) -> int:  # type: ignore[no-untyped-def]
        return int((await db.execute(stmt)).scalar() or 0)

    runs_24h = select(AnalysisRun).where(AnalysisRun.window_end >= day_ago).subquery()
    lines_24h = await scalar(select(func.sum(runs_24h.c.lines_count)))
    errors_24h = await scalar(select(func.sum(runs_24h.c.error_lines_count)))
    cycles_24h = await scalar(select(func.count()).select_from(runs_24h))
    cycles_failed = await scalar(
        select(func.count())
        .select_from(AnalysisRun)
        .where(AnalysisRun.window_end >= day_ago, AnalysisRun.status == RunStatus.failed)
    )
    projects_with_errors = await scalar(
        select(func.count(func.distinct(AnalysisRun.container_id))).where(
            AnalysisRun.window_end >= hour_ago, AnalysisRun.error_lines_count > 0
        )
    )

    # Projetos mais ativos nas últimas 24 h, por linhas processadas.
    activity_rows = (
        await db.execute(
            select(
                Container.id,
                Container.name,
                Container.state,
                Host.name,
                func.coalesce(func.sum(AnalysisRun.lines_count), 0).label("lines"),
                func.coalesce(func.sum(AnalysisRun.error_lines_count), 0).label("errors"),
            )
            .join(Host, Host.id == Container.host_id)
            .outerjoin(
                AnalysisRun,
                (AnalysisRun.container_id == Container.id) & (AnalysisRun.window_end >= day_ago),
            )
            .where(
                Container.monitored.is_(True),
                Container.state != ContainerState.removed,
                Host.status != HostStatus.removed,
            )
            .group_by(Container.id, Container.name, Container.state, Host.name)
            .order_by(
                func.coalesce(func.sum(AnalysisRun.error_lines_count), 0).desc(),
                func.coalesce(func.sum(AnalysisRun.lines_count), 0).desc(),
            )
            .limit(6)
        )
    ).all()
    triggers_by_container = dict(
        (
            await db.execute(
                select(TriggerFired.container_id, func.count())
                .where(TriggerFired.fired_at >= day_ago)
                .group_by(TriggerFired.container_id)
            )
        ).all()
    )

    from lognix.settings.service import ai_is_active

    return SummaryOut(
        hosts_total=len(hosts),
        hosts_connected=sum(1 for h in hosts if h.status == HostStatus.connected),
        projects_total=sum(monitored_by_host.values()),
        projects_with_errors_1h=projects_with_errors,
        notifications_new=await scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.status == NotificationStatus.new)
        ),
        triggers_new_24h=await scalar(
            select(func.count()).select_from(TriggerFired).where(TriggerFired.fired_at >= day_ago)
        ),
        triggers_unanalyzed=await scalar(
            select(func.count()).select_from(TriggerFired).where(TriggerFired.insight_id.is_(None))
        ),
        lines_24h=lines_24h,
        errors_24h=errors_24h,
        cycles_24h=cycles_24h,
        cycles_failed_24h=cycles_failed,
        ai_enabled=await ai_is_active(db),
        **await _series(db, day_ago),
        hosts=[
            HostSummary(
                id=h.id,
                name=h.name,
                status=h.status,
                monitored=monitored_by_host.get(h.id, 0),
                last_error=h.last_error,
            )
            for h in hosts
        ],
        top_projects=[
            ProjectActivity(
                id=row[0],
                name=row[1],
                state=row[2],
                host_name=row[3],
                lines_24h=int(row[4]),
                errors_24h=int(row[5]),
                triggers_24h=int(triggers_by_container.get(row[0], 0)),
            )
            for row in activity_rows
        ],
    )
