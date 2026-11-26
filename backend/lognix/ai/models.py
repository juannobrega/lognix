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
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class ProviderStatus(enum.StrEnum):
    unknown = "unknown"
    ok = "ok"
    error = "error"


class AiProviderConfig(Base):
    """Um provider configurado. A ordem de `priority` é a cadeia de fallback."""

    __tablename__ = "ai_providers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    #: Credenciais e opções, criptografadas em bloco. Nunca voltam pela API.
    credentials_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    #: Nomes das chaves presentes, para a interface saber o que já foi preenchido.
    credential_keys: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    default_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_status: Mapped[ProviderStatus] = mapped_column(
        Enum(ProviderStatus, name="provider_status"), nullable=False, default=ProviderStatus.unknown
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    models: Mapped[list[AiModelConfig]] = relationship(
        back_populates="provider", cascade="all, delete-orphan", lazy="selectin"
    )


class AiModelConfig(Base):
    """Um modelo habilitado num provider, com o preço que o Lognix usa para estimar custo."""

    __tablename__ = "ai_models"
    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_ai_models_provider_model"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Preço por milhão de tokens. Vem do catálogo quando o provider informa, senão é manual.
    prompt_usd_per_mtok: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    completion_usd_per_mtok: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    provider: Mapped[AiProviderConfig] = relationship(back_populates="models")


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
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="openrouter")
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    #: Posição na cadeia de fallback: 0 é o provider preferido.
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fell_back: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
