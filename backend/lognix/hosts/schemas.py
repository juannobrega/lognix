from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from lognix.hosts.models import HostStatus, SshAuthMethod

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")


class TunnelStateOut(BaseModel):
    socket_path: str | None
    connected_since: datetime | None
    last_check_at: datetime | None
    reconnect_attempts: int
    last_error: str | None

    model_config = {"from_attributes": True}


class HostOut(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    ssh_port: int
    ssh_user: str
    ssh_auth_method: SshAuthMethod
    ssh_host_key_fingerprint: str | None
    runtime: str
    docker_version: str | None
    status: HostStatus
    last_error: str | None
    created_at: datetime
    tunnel: TunnelStateOut | None = None

    model_config = {"from_attributes": True}


class HostCredentialsIn(BaseModel):
    ssh_auth_method: SshAuthMethod
    private_key: str | None = Field(default=None, max_length=20_000)
    key_passphrase: str | None = Field(default=None, max_length=512)
    password: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _check_fields(self) -> HostCredentialsIn:
        m = self.ssh_auth_method
        if m in (SshAuthMethod.key, SshAuthMethod.key_passphrase) and not self.private_key:
            raise ValueError("private_key é obrigatória para autenticação por chave")
        if m == SshAuthMethod.key_passphrase and not self.key_passphrase:
            raise ValueError("key_passphrase é obrigatória para chave com passphrase")
        if m == SshAuthMethod.password and not self.password:
            raise ValueError("password é obrigatória para autenticação por senha")
        return self


class HostCreate(HostCredentialsIn):
    name: str = Field(pattern=NAME_RE.pattern, max_length=63)
    address: str = Field(min_length=1, max_length=253)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(min_length=1, max_length=64)


class HostUpdate(BaseModel):
    name: str | None = Field(default=None, pattern=NAME_RE.pattern, max_length=63)
    address: str | None = Field(default=None, min_length=1, max_length=253)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ssh_user: str | None = Field(default=None, min_length=1, max_length=64)
    credentials: HostCredentialsIn | None = None


class ValidationStepOut(BaseModel):
    number: int
    name: str
    status: Literal["pending", "running", "ok", "failed"]
    message: str | None = None
    action: str | None = None
    detail: str | None = None


class ContainerSummary(BaseModel):
    docker_id: str
    name: str
    image: str
    state: str
    status: str
    compose_project: str | None = None
    compose_service: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class ValidationOut(BaseModel):
    id: uuid.UUID
    host_id: uuid.UUID
    status: Literal["running", "ok", "failed"]
    steps: list[ValidationStepOut]
    containers: list[ContainerSummary] | None = None
    started_at: datetime
    finished_at: datetime | None = None


class HostCreatedOut(BaseModel):
    host: HostOut
    validation_id: uuid.UUID


class PurgeIn(BaseModel):
    confirm_name: str
