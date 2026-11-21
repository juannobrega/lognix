from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lognix.db import Base
from lognix.hosts.models import Host


class ContainerState(enum.StrEnum):
    created = "created"
    running = "running"
    restarting = "restarting"
    paused = "paused"
    exited = "exited"
    dead = "dead"
    removed = "removed"  # sumiu do host; mantido para histórico


class Container(Base):
    __tablename__ = "containers"
    __table_args__ = (UniqueConstraint("host_id", "docker_id", name="uq_containers_host_docker"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    host_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    docker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    image: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    image_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    compose_project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    compose_service: Mapped[str | None] = mapped_column(String(255), nullable=True)
    labels: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    state: Mapped[ContainerState] = mapped_column(
        Enum(ContainerState, name="container_state"), nullable=False
    )
    monitored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    monitored_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    host: Mapped[Host] = relationship(lazy="selectin")


class AlloyConfigVersion(Base):
    __tablename__ = "alloy_config_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reload_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
