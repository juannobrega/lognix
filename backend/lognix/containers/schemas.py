from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from lognix.containers.models import ContainerState


class ContainerOut(BaseModel):
    id: uuid.UUID
    host_id: uuid.UUID
    docker_id: str
    name: str
    image: str
    image_digest: str | None
    compose_project: str | None
    compose_service: str | None
    labels: dict[str, str]
    state: ContainerState
    monitored: bool
    monitored_since: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    kind: str = "image"

    model_config = {"from_attributes": True}


class ProjectOut(ContainerOut):
    host_name: str
    host_status: str


class MonitoredIn(BaseModel):
    container_ids: list[uuid.UUID] = Field(default_factory=list)


class AlloyApplyOut(BaseModel):
    version_id: int | None
    reload_ok: bool
    error: str | None = None
    hosts_in_config: int
    containers_in_config: int


class MonitoredOut(BaseModel):
    containers: list[ContainerOut]
    alloy: AlloyApplyOut


class AlloyConfigVersionOut(BaseModel):
    id: int
    hash: str
    reason: str
    applied_at: datetime
    reload_ok: bool
    error: str | None

    model_config = {"from_attributes": True}


class AlloyConfigOut(BaseModel):
    current: str
    path: str
    versions: list[AlloyConfigVersionOut]
