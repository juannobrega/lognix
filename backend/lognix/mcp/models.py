"""Chaves de acesso ao servidor MCP. Ver ADR 017."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from lognix.db import Base, TimestampMixin


class McpScope(enum.StrEnum):
    """O que uma chave pode fazer. A diferença entre eles é o estrago se a chave vazar."""

    #: Hosts, projetos, logs, padrões, insights, ocorrências. Expõe seus logs.
    leitura = "leitura"
    #: Disparar análise. Além de expor, **gasta dinheiro** com IA.
    analise = "analise"
    #: Consumo, estado do sistema, provedores sem credencial. Expõe custos e topologia.
    admin = "admin"


class McpKey(Base, TimestampMixin):
    __tablename__ = "mcp_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    #: Os primeiros caracteres, em claro, só para a pessoa reconhecer qual chave é qual.
    prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    #: Argon2 do valor completo. O valor em si aparece uma vez e nunca mais: chave que pode ser
    #: relida é chave que vaza pelo backup e pela tela de quem compartilha o monitor.
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def ativa(self, agora: datetime) -> bool:
        return self.enabled and (self.expires_at is None or self.expires_at > agora)


class McpCall(Base, TimestampMixin):
    """Uma chamada de ferramenta. Sem isto não há como responder quem consultou o quê."""

    __tablename__ = "mcp_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    key_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    tool: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
