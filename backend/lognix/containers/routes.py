"""Rotas: containers por host, seleção de monitorados, config do Alloy, projetos."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from lognix.alloy.service import get_alloy_manager
from lognix.auth.deps import CurrentUser, DbSession
from lognix.containers import service
from lognix.containers.models import Container
from lognix.containers.schemas import (
    AlloyApplyOut,
    AlloyConfigOut,
    AlloyConfigVersionOut,
    ContainerOut,
    MonitoredIn,
    MonitoredOut,
    ProjectOut,
)
from lognix.docker.client import DockerApiError, DockerClient
from lognix.errors import ApiError
from lognix.hosts.models import Host, HostStatus
from lognix.hosts.supervisor import get_supervisor

hosts_router = APIRouter(prefix="/hosts", tags=["containers"])
projects_router = APIRouter(prefix="/projects", tags=["projects"])


def _out(c: Container) -> ContainerOut:
    out = ContainerOut.model_validate(c)
    out.kind = "image"  # "github" quando houver RepositoryLink (fase 1.1)
    return out


async def _host(db: DbSession, host_id: uuid.UUID) -> Host:
    host = await db.get(Host, host_id)
    if host is None or host.status == HostStatus.removed:
        raise ApiError(404, "not_found", "Host não encontrado.")
    return host


@hosts_router.get("/{host_id}/containers", response_model=list[ContainerOut])
async def list_containers(host_id: uuid.UUID, _: CurrentUser, db: DbSession) -> list[ContainerOut]:
    host = await _host(db, host_id)
    socket_path = get_supervisor().socket_path(host.id)
    if socket_path is not None:
        client = DockerClient(socket_path)
        try:
            raw = await client.containers(all=True)
        except DockerApiError as exc:
            raise ApiError(502, "docker_error", str(exc)) from exc
        finally:
            await client.aclose()
        containers, monitored_changed = await service.sync_inventory(db, host, raw)
        if monitored_changed:
            await get_alloy_manager().apply(
                f"host {host.name}: container monitorado desapareceu do inventário"
            )
        return [_out(c) for c in sorted(containers, key=lambda c: c.name)]
    # Desconectado: devolve o último inventário conhecido.
    return [_out(c) for c in await service.list_for_host(db, host.id)]


@hosts_router.put("/{host_id}/containers/monitored", response_model=MonitoredOut)
async def set_monitored(
    host_id: uuid.UUID, body: MonitoredIn, _: CurrentUser, db: DbSession
) -> MonitoredOut:
    host = await _host(db, host_id)
    containers = await service.set_monitored(db, host, set(body.container_ids))
    names = ", ".join(c.name for c in containers if c.monitored) or "nenhum"
    result = await get_alloy_manager().apply(f"host {host.name}: monitorados = {names}")
    return MonitoredOut(
        containers=[_out(c) for c in containers],
        alloy=AlloyApplyOut(
            version_id=result.version_id,
            reload_ok=result.reload_ok,
            error=result.error,
            hosts_in_config=result.hosts_in_config,
            containers_in_config=result.containers_in_config,
        ),
    )


@hosts_router.get("/{host_id}/alloy-config", response_model=AlloyConfigOut)
async def alloy_config(host_id: uuid.UUID, _: CurrentUser, db: DbSession) -> AlloyConfigOut:
    await _host(db, host_id)
    manager = get_alloy_manager()
    return AlloyConfigOut(
        current=manager.current_content() or "",
        path=manager.config_path,
        versions=[AlloyConfigVersionOut.model_validate(v) for v in await manager.versions()],
    )


@projects_router.get("", response_model=list[ProjectOut])
async def list_projects(_: CurrentUser, db: DbSession) -> list[ProjectOut]:
    out = []
    for c in await service.list_projects(db):
        base = _out(c).model_dump()
        out.append(ProjectOut(**base, host_name=c.host.name, host_status=c.host.status))
    return out


@projects_router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, _: CurrentUser, db: DbSession) -> ProjectOut:
    c = await db.get(Container, project_id)
    if c is None or c.host.status == HostStatus.removed:
        raise ApiError(404, "not_found", "Projeto não encontrado.")
    base = _out(c).model_dump()
    return ProjectOut(**base, host_name=c.host.name, host_status=c.host.status)
