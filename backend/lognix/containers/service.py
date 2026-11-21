"""Inventário e seleção de monitorados."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.containers.models import Container, ContainerState
from lognix.docker.client import summarize_container
from lognix.hosts.models import Host, HostStatus


def _state(raw: str) -> ContainerState:
    try:
        return ContainerState(raw)
    except ValueError:
        return ContainerState.created


async def sync_inventory(
    db: AsyncSession, host: Host, raw: list[dict[str, Any]]
) -> tuple[list[Container], bool]:
    """Reconcilia o inventário do host com a lista vinda do Docker.

    Devolve (containers presentes, houve mudança em monitorados). Containers que sumiram
    ficam `removed` e deixam de ser monitorados; nesse caso a config do Alloy precisa ser
    reaplicada pelo chamador. Reconhecimento de redeploy por identidade de serviço entra na 0.5.0.
    """
    now = datetime.now(UTC)
    existing = {
        c.docker_id: c
        for c in (await db.execute(select(Container).where(Container.host_id == host.id))).scalars()
    }
    present: list[Container] = []
    seen: set[str] = set()
    for item in raw:
        s = summarize_container(item)
        seen.add(s["docker_id"])
        c = existing.get(s["docker_id"])
        if c is None:
            c = Container(
                id=uuid.uuid4(),
                host_id=host.id,
                docker_id=s["docker_id"],
                first_seen_at=now,
            )
            db.add(c)
        c.name = s["name"]
        c.image = s["image"]
        c.image_digest = item.get("ImageID") or None
        c.compose_project = s["compose_project"]
        c.compose_service = s["compose_service"]
        c.labels = s["labels"]
        c.state = _state(s["state"])
        c.last_seen_at = now
        present.append(c)
    monitored_changed = False
    for docker_id, c in existing.items():
        if docker_id not in seen and c.state != ContainerState.removed:
            c.state = ContainerState.removed
            if c.monitored:
                c.monitored = False
                monitored_changed = True
    await db.commit()
    for c in present:
        await db.refresh(c)
    return present, monitored_changed


async def list_for_host(db: AsyncSession, host_id: uuid.UUID) -> list[Container]:
    stmt = (
        select(Container)
        .where(Container.host_id == host_id, Container.state != ContainerState.removed)
        .order_by(Container.name)
    )
    return list((await db.execute(stmt)).scalars())


async def set_monitored(db: AsyncSession, host: Host, ids: set[uuid.UUID]) -> list[Container]:
    now = datetime.now(UTC)
    containers = await list_for_host(db, host.id)
    for c in containers:
        want = c.id in ids
        if want and not c.monitored:
            c.monitored = True
            c.monitored_since = now
        elif not want and c.monitored:
            c.monitored = False
    await db.commit()
    for c in containers:
        await db.refresh(c)
    return containers


async def monitored_by_host(db: AsyncSession) -> list[tuple[Host, list[Container]]]:
    """Hosts não removidos com seus containers monitorados. Base da config do Alloy."""
    hosts = list(
        (
            await db.execute(
                select(Host).where(Host.status != HostStatus.removed).order_by(Host.name)
            )
        ).scalars()
    )
    result: list[tuple[Host, list[Container]]] = []
    for host in hosts:
        stmt = (
            select(Container)
            .where(
                Container.host_id == host.id,
                Container.monitored.is_(True),
                Container.state != ContainerState.removed,
            )
            .order_by(Container.name)
        )
        containers = list((await db.execute(stmt)).scalars())
        if containers:
            result.append((host, containers))
    return result


async def list_projects(db: AsyncSession) -> list[Container]:
    stmt = (
        select(Container)
        .join(Host, Host.id == Container.host_id)
        .where(
            Container.monitored.is_(True),
            Container.state != ContainerState.removed,
            Host.status != HostStatus.removed,
        )
        .order_by(Host.name, Container.name)
    )
    return list((await db.execute(stmt)).scalars())
