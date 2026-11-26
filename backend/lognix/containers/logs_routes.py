"""GET /projects/{id}/logs: histórico via LogQL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from lognix.auth.deps import CurrentUser, DbSession
from lognix.containers.models import Container
from lognix.errors import ApiError
from lognix.hosts.models import HostStatus
from lognix.loki.client import LokiClient, LokiError, selector

router = APIRouter(prefix="/projects", tags=["logs"])


class LogLineOut(BaseModel):
    ts_ns: str
    line: str
    labels: dict[str, str]


class LogsOut(BaseModel):
    lines: list[LogLineOut]
    has_more: bool
    oldest_ts_ns: str | None
    newest_ts_ns: str | None
    query: str
    monitored_since: datetime | None


@router.get("/{project_id}/logs", response_model=LogsOut)
async def project_logs(
    project_id: uuid.UUID,
    _: CurrentUser,
    db: DbSession,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
    direction: Annotated[Literal["backward", "forward"], Query()] = "backward",
) -> LogsOut:
    project = await db.get(Container, project_id)
    if project is None or project.host.status == HostStatus.removed:
        raise ApiError(404, "not_found", "Projeto não encontrado.")
    now = datetime.now(UTC)
    end_dt = end or now
    start_dt = start or (end_dt - timedelta(minutes=15))
    if start_dt >= end_dt:
        raise ApiError(400, "bad_range", "start precisa ser anterior a end.")
    if end_dt - start_dt > timedelta(days=16):
        raise ApiError(400, "bad_range", "Janela máxima de 16 dias.")
    query = selector(project_id, text=q)
    client = LokiClient()
    try:
        lines = await client.query_range(
            query,
            start_ns=int(start_dt.timestamp() * 1e9),
            end_ns=int(end_dt.timestamp() * 1e9),
            limit=limit,
            direction=direction,
        )
    except LokiError as exc:
        raise ApiError(
            502, "loki_error", str(exc), "Verifique o estado do Loki em Sistema."
        ) from exc
    finally:
        await client.aclose()
    return LogsOut(
        lines=[LogLineOut(**ln.to_dict()) for ln in lines],
        has_more=len(lines) >= limit,
        oldest_ts_ns=str(lines[0].ts_ns) if lines else None,
        newest_ts_ns=str(lines[-1].ts_ns) if lines else None,
        query=query,
        monitored_since=project.monitored_since,
    )
