from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lognix.db import Base, TimestampMixin


class Runtime(enum.StrEnum):
    docker = "docker"


class SshAuthMethod(enum.StrEnum):
    key = "key"
    key_passphrase = "key_passphrase"  # noqa: S105
    password = "password"  # noqa: S105


class HostStatus(enum.StrEnum):
    pending = "pending"
    connected = "connected"
    disconnected = "disconnected"
    error = "error"
    removed = "removed"


class Host(TimestampMixin, Base):
    __tablename__ = "hosts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String(253), nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    ssh_user: Mapped[str] = mapped_column(String(64), nullable=False)
    ssh_auth_method: Mapped[SshAuthMethod] = mapped_column(
        Enum(SshAuthMethod, name="ssh_auth_method"), nullable=False
    )
    ssh_private_key_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ssh_key_passphrase_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ssh_password_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ssh_host_key_fingerprint: Mapped[str | None] = mapped_column(String(120), nullable=True)
    runtime: Mapped[Runtime] = mapped_column(
        Enum(Runtime, name="runtime"), nullable=False, default=Runtime.docker
    )
    docker_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[HostStatus] = mapped_column(
        Enum(HostStatus, name="host_status"), nullable=False, default=HostStatus.pending
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tunnel: Mapped[TunnelState | None] = relationship(
        back_populates="host", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )


class TunnelState(Base):
    __tablename__ = "tunnel_states"

    host_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True
    )
    socket_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    connected_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconnect_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    host: Mapped[Host] = relationship(back_populates="tunnel")
