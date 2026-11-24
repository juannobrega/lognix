from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from lognix.db import Base


class Severity(enum.StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class InsightStatus(enum.StrEnum):
    new = "new"
    seen = "seen"


class AiPurpose(enum.StrEnum):
    analyze = "analyze"
    code_diagnosis = "code_diagnosis"
    issue_text = "issue_text"
    test = "test"


class AiCallStatus(enum.StrEnum):
    ok = "ok"
    error = "error"


class CostSource(enum.StrEnum):
    provider = "provider"
    estimated = "estimated"
    unknown = "unknown"


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    container_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("triggers_fired.id", ondelete="CASCADE"), nullable=False
    )
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="severity"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    probable_cause: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    needs_code: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Evidências resolvidas pelo backend a partir dos índices devolvidos pela IA.
    evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    code_diagnosis: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    context_truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Contexto exato enviado ao provider. Transparência: Guardrails seção 1.
    sent_context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[InsightStatus] = mapped_column(
        Enum(InsightStatus, name="insight_status"),
        nullable=False,
        default=InsightStatus.new,
        index=True,
    )
    seen_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class AiCall(Base):
    __tablename__ = "ai_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trigger_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("triggers_fired.id", ondelete="SET NULL"), nullable=True
    )
    insight_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insights.id", ondelete="SET NULL"), nullable=True
    )
    container_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="openrouter")
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    purpose: Mapped[AiPurpose] = mapped_column(Enum(AiPurpose, name="ai_purpose"), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    cost_source: Mapped[CostSource] = mapped_column(
        Enum(CostSource, name="cost_source"), nullable=False, default=CostSource.unknown
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_retry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[AiCallStatus] = mapped_column(
        Enum(AiCallStatus, name="ai_call_status"), nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
