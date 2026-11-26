from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from lognix.db import Base


class LogLevel(enum.StrEnum):
    error = "error"
    warn = "warn"
    info = "info"
    debug = "debug"
    unknown = "unknown"


class RunStatus(enum.StrEnum):
    ok = "ok"
    skipped = "skipped"
    failed = "failed"


class TriggerType(enum.StrEnum):
    error = "error"
    docker_event = "docker_event"
    anomaly = "anomaly"
    manual = "manual"


class Pattern(Base):
    __tablename__ = "patterns"
    __table_args__ = (
        UniqueConstraint("container_id", "template", name="uq_patterns_container_template"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[LogLevel] = mapped_column(Enum(LogLevel, name="log_level"), nullable=False)
    count_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sample: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ignored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    container_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    lines_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_lines_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warn_lines_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_patterns_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_called: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="run_status"), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TriggerFired(Base):
    __tablename__ = "triggers_fired"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True
    )
    container_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[TriggerType] = mapped_column(
        Enum(TriggerType, name="trigger_type"), nullable=False
    )
    reason: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    fired_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    insight_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sample_lines: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
