from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from lognix.auth.deps import CurrentUser, DbSession
from lognix.containers.models import Container
from lognix.errors import ApiError
from lognix.events import service
from lognix.events.models import DockerEventType, HostEventType
from lognix.hosts.models import Host, HostStatus

hosts_router = APIRouter(prefix="/hosts", tags=["events"])
projects_router = APIRouter(prefix="/projects", tags=["events"])


class HostEventOut(BaseModel):
    id: int
    type: HostEventType
    attributes: dict[str, Any]
    occurred_at: datetime

    model_config = {"from_attributes": True}


class DockerEventOut(BaseModel):
    id: int
    type: DockerEventType
    exit_code: int | None
    attributes: dict[str, Any]
    previous_image: str | None
    new_image: str | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


@hosts_router.get("/{host_id}/events", response_model=list[HostEventOut])
async def host_events(host_id: uuid.UUID, _: CurrentUser, db: DbSession) -> list[HostEventOut]:
    host = await db.get(Host, host_id)
    if host is None:
        raise ApiError(404, "not_found", "Host não encontrado.")
    return [HostEventOut.model_validate(e) for e in await service.list_host_events(db, host_id)]


@projects_router.get("/{project_id}/events", response_model=list[DockerEventOut])
async def project_events(
    project_id: uuid.UUID, _: CurrentUser, db: DbSession
) -> list[DockerEventOut]:
    c = await db.get(Container, project_id)
    if c is None or c.host.status == HostStatus.removed:
        raise ApiError(404, "not_found", "Projeto não encontrado.")
    return [
        DockerEventOut.model_validate(e)
        for e in await service.list_container_events(db, project_id)
    ]
