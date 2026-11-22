"""Inventário e seleção de monitorados."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.containers.models import Container, ContainerState
from lognix.hosts.models import Host, HostStatus


async def sync_inventory(
    db: AsyncSession, host: Host, raw: list[dict[str, Any]]
) -> tuple[list[Container], bool]:
    """Compatibilidade: delega à reconciliação completa em lognix.events.service."""
    from lognix.events.service import sync_inventory as full_sync

    result = await full_sync(db, host, raw)
    return result.present, result.monitored_changed


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


async def list_excluded(db: AsyncSession) -> list[Container]:
    stmt = (
        select(Container)
        .join(Host, Host.id == Container.host_id)
        .where(Container.state == ContainerState.removed, Host.status != HostStatus.removed)
        .order_by(Container.last_seen_at.desc())
    )
    return list((await db.execute(stmt)).scalars())


async def list_excluded_for_host(db: AsyncSession, host_id: uuid.UUID) -> list[Container]:
    stmt = (
        select(Container)
        .where(Container.host_id == host_id, Container.state == ContainerState.removed)
        .order_by(Container.last_seen_at.desc())
    )
    return list((await db.execute(stmt)).scalars())
