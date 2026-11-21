"""Rotas /hosts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from lognix.auth.deps import CurrentUser, DbSession
from lognix.docker.client import DockerApiError, DockerClient, summarize_container
from lognix.errors import ApiError
from lognix.hosts import credentials
from lognix.hosts.models import Host, HostStatus
from lognix.hosts.schemas import (
    ContainerSummary,
    HostCreate,
    HostCreatedOut,
    HostOut,
    HostUpdate,
    PurgeIn,
    ValidationOut,
    ValidationStepOut,
)
from lognix.hosts.supervisor import get_supervisor
from lognix.hosts.validation import ValidationRun, registry

router = APIRouter(prefix="/hosts", tags=["hosts"])


def _validation_out(run: ValidationRun) -> ValidationOut:
    return ValidationOut(
        id=run.id,
        host_id=run.host_id,
        status=run.status,
        steps=[
            ValidationStepOut(
                number=s.number,
                name=s.name,
                status=s.status,
                message=s.message,
                action=s.action,
                detail=s.detail,
            )
            for s in run.steps
        ],
        containers=[ContainerSummary(**c) for c in run.containers]
        if run.containers is not None
        else None,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


async def _get_host(db: DbSession, host_id: uuid.UUID, *, include_removed: bool = False) -> Host:
    host = await db.get(Host, host_id)
    if host is None or (host.status == HostStatus.removed and not include_removed):
        raise ApiError(404, "not_found", "Host não encontrado.")
    return host


@router.get("", response_model=list[HostOut])
async def list_hosts(_: CurrentUser, db: DbSession) -> list[HostOut]:
    hosts = (
        await db.execute(
            select(Host).where(Host.status != HostStatus.removed).order_by(Host.created_at)
        )
    ).scalars()
    return [HostOut.model_validate(h) for h in hosts]


@router.post("", response_model=HostCreatedOut, status_code=status.HTTP_202_ACCEPTED)
async def create_host(body: HostCreate, user: CurrentUser, db: DbSession) -> HostCreatedOut:
    exists = (await db.execute(select(Host).where(Host.name == body.name))).scalar_one_or_none()
    if exists is not None and exists.status != HostStatus.removed:
        raise ApiError(409, "name_taken", "Já existe um host com este nome.")
    host = Host(
        id=uuid.uuid4(),
        name=body.name,
        address=body.address,
        ssh_port=body.ssh_port,
        ssh_user=body.ssh_user,
        ssh_auth_method=body.ssh_auth_method,
        created_by=user.id,
        status=HostStatus.pending,
    )
    credentials.apply(host, body)
    db.add(host)
    await db.commit()
    await db.refresh(host)
    run = registry.start(host, get_supervisor())
    return HostCreatedOut(host=HostOut.model_validate(host), validation_id=run.id)


@router.get("/validations/{validation_id}", response_model=ValidationOut)
async def get_validation(validation_id: uuid.UUID, _: CurrentUser) -> ValidationOut:
    run = registry.get(validation_id)
    if run is None:
        raise ApiError(404, "not_found", "Validação não encontrada ou expirada.")
    return _validation_out(run)


@router.get("/{host_id}", response_model=HostOut)
async def get_host(host_id: uuid.UUID, _: CurrentUser, db: DbSession) -> HostOut:
    return HostOut.model_validate(await _get_host(db, host_id))


@router.put("/{host_id}", response_model=HostCreatedOut, status_code=status.HTTP_202_ACCEPTED)
async def update_host(
    host_id: uuid.UUID, body: HostUpdate, _: CurrentUser, db: DbSession
) -> HostCreatedOut:
    host = await _get_host(db, host_id)
    if body.name and body.name != host.name:
        dup = (await db.execute(select(Host).where(Host.name == body.name))).scalar_one_or_none()
        if dup is not None:
            raise ApiError(409, "name_taken", "Já existe um host com este nome.")
        host.name = body.name
    address_changed = False
    if body.address and body.address != host.address:
        host.address = body.address
        address_changed = True
    if body.ssh_port and body.ssh_port != host.ssh_port:
        host.ssh_port = body.ssh_port
        address_changed = True
    if body.ssh_user:
        host.ssh_user = body.ssh_user
    if body.credentials:
        credentials.apply(host, body.credentials)
    if address_changed:
        # Outro endereço é outro servidor: o fingerprint anterior não vale.
        host.ssh_host_key_fingerprint = None
    host.status = HostStatus.pending
    host.last_error = None
    host.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(host)
    run = registry.start(host, get_supervisor())
    return HostCreatedOut(host=HostOut.model_validate(host), validation_id=run.id)


@router.post(
    "/{host_id}/reconnect", response_model=HostCreatedOut, status_code=status.HTTP_202_ACCEPTED
)
async def reconnect(host_id: uuid.UUID, _: CurrentUser, db: DbSession) -> HostCreatedOut:
    host = await _get_host(db, host_id)
    host.status = HostStatus.pending
    host.last_error = None
    await db.commit()
    await db.refresh(host)
    run = registry.start(host, get_supervisor())
    return HostCreatedOut(host=HostOut.model_validate(host), validation_id=run.id)


@router.post(
    "/{host_id}/accept-fingerprint",
    response_model=HostCreatedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def accept_fingerprint(host_id: uuid.UUID, _: CurrentUser, db: DbSession) -> HostCreatedOut:
    host = await _get_host(db, host_id)
    host.ssh_host_key_fingerprint = None
    host.status = HostStatus.pending
    host.last_error = None
    await db.commit()
    await db.refresh(host)
    run = registry.start(host, get_supervisor())
    return HostCreatedOut(host=HostOut.model_validate(host), validation_id=run.id)


@router.delete("/{host_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_host(
    host_id: uuid.UUID,
    _: CurrentUser,
    db: DbSession,
    purge: Annotated[bool, Query()] = False,
    body: PurgeIn | None = None,
) -> None:
    host = await _get_host(db, host_id, include_removed=purge)
    await get_supervisor().remove(host.id)
    if purge:
        if body is None or body.confirm_name != host.name:
            raise ApiError(
                400,
                "confirm_required",
                "Para apagar de fato, envie o nome do host em confirm_name.",
            )
        await db.delete(host)
    else:
        host.status = HostStatus.removed
        host.updated_at = datetime.now(UTC)
    await db.commit()


@router.get("/{host_id}/containers", response_model=list[ContainerSummary])
async def list_containers(
    host_id: uuid.UUID, _: CurrentUser, db: DbSession
) -> list[ContainerSummary]:
    host = await _get_host(db, host_id)
    socket_path = get_supervisor().socket_path(host.id)
    if socket_path is None:
        raise ApiError(
            409,
            "host_disconnected",
            "O host não está conectado.",
            "Use Reconectar e aguarde o túnel ficar ativo.",
        )
    client = DockerClient(socket_path)
    try:
        raw = await client.containers(all=True)
    except DockerApiError as exc:
        raise ApiError(502, "docker_error", str(exc)) from exc
    finally:
        await client.aclose()
    return [ContainerSummary(**summarize_container(c)) for c in raw]
