from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from lognix.db import Base


class DockerEventType(enum.StrEnum):
    start = "start"
    die = "die"
    oom = "oom"
    restart = "restart"
    kill = "kill"
    stop = "stop"
    pause = "pause"
    unpause = "unpause"
    health_status = "health_status"
    destroy = "destroy"
    redeploy = "redeploy"  # sintético, gerado pelo Lognix


class HostEventType(enum.StrEnum):
    connected = "connected"
    disconnected = "disconnected"
    new_container = "new_container"
    container_removed = "container_removed"
    inventory_synced = "inventory_synced"
    events_stream_restarted = "events_stream_restarted"
    error = "error"


class DockerEvent(Base):
    __tablename__ = "docker_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    container_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[DockerEventType] = mapped_column(
        Enum(DockerEventType, name="docker_event_type"), nullable=False
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    previous_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    new_image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class HostEvent(Base):
    __tablename__ = "host_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    host_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[HostEventType] = mapped_column(
        Enum(HostEventType, name="host_event_type"), nullable=False
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
