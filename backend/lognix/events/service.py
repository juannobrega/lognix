"""Reconciliação de inventário com redeploy por identidade de serviço, e registro de eventos."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.containers.models import Container, ContainerState
from lognix.docker.client import summarize_container
from lognix.events.models import DockerEvent, DockerEventType, HostEvent, HostEventType
from lognix.hosts.models import Host
from lognix.notifications.models import NotificationType
from lognix.notifications.service import notify

log = logging.getLogger(__name__)

REDEPLOY_WINDOW = timedelta(minutes=10)
# `docker compose up` renomeia o container antigo para `<12 hex>_<nome>` antes de criar o novo.
# Enquanto os dois coexistem, o antigo é um zumbi prestes a ser destruído.
COMPOSE_RENAME_RE = re.compile(r"^[0-9a-f]{12}_")

# Uma reconciliação por host de cada vez: validação, worker e rota podem coincidir e, sem isso,
# dois inserts do mesmo container disputam a unicidade (host_id, docker_id).
_sync_locks: dict[uuid.UUID, asyncio.Lock] = {}


def _lock_for(host_id: uuid.UUID) -> asyncio.Lock:
    lock = _sync_locks.get(host_id)
    if lock is None:
        lock = _sync_locks[host_id] = asyncio.Lock()
    return lock


# Ações do Docker que viram DockerEvent, e quais exigem container monitorado para serem gravadas.
RECORDED_ACTIONS: dict[str, DockerEventType] = {
    "start": DockerEventType.start,
    "die": DockerEventType.die,
    "oom": DockerEventType.oom,
    "restart": DockerEventType.restart,
    "kill": DockerEventType.kill,
    "stop": DockerEventType.stop,
    "pause": DockerEventType.pause,
    "unpause": DockerEventType.unpause,
    "destroy": DockerEventType.destroy,
}


def _state(raw: str) -> ContainerState:
    try:
        return ContainerState(raw)
    except ValueError:
        return ContainerState.created


def _identity(c: Container | dict[str, Any]) -> tuple[str, str | None, str | None]:
    if isinstance(c, dict):
        return (c["name"], c["compose_project"], c["compose_service"])
    return (c.name, c.compose_project, c.compose_service)


def _same_service(
    a: tuple[str, str | None, str | None], b: tuple[str, str | None, str | None]
) -> bool:
    name_a, proj_a, svc_a = a
    name_b, proj_b, svc_b = b
    if proj_a and svc_a and proj_b and svc_b:
        return proj_a == proj_b and svc_a == svc_b
    return name_a == name_b


class SyncResult:
    def __init__(self) -> None:
        self.present: list[Container] = []
        self.new: list[Container] = []
        self.removed: list[Container] = []
        self.redeployed: list[tuple[Container, str, str]] = []  # (container, prev_image, new_image)
        self.removed_monitored: list[Container] = []
        self.first_sync = False

    @property
    def monitored_changed(self) -> bool:
        return any(c.monitored for c, _, _ in self.redeployed) or bool(self.removed_monitored)


async def sync_inventory(db: AsyncSession, host: Host, raw: list[dict[str, Any]]) -> SyncResult:
    async with _lock_for(host.id):
        return await _sync_inventory(db, host, raw)


async def _sync_inventory(db: AsyncSession, host: Host, raw: list[dict[str, Any]]) -> SyncResult:
    """Reconcilia o inventário do host com a lista vinda do Docker.

    - Container novo: criado como não monitorado, notificação `new_container`.
    - Container sumiu: `removed`, deixa de ser monitorado, evento `container_removed`.
    - Redeploy: container novo com a mesma identidade de serviço de um removido há menos de
      10 min **ou removido neste mesmo sync** mantém o `Container.id`, atualiza docker_id e
      imagem, continua monitorado e grava `DockerEvent.redeploy`. Nenhuma notificação.
    """
    now = datetime.now(UTC)
    result = SyncResult()
    existing = {
        c.docker_id: c
        for c in (await db.execute(select(Container).where(Container.host_id == host.id))).scalars()
    }
    result.first_sync = not existing
    summaries = [summarize_container(item) | {"_raw": item} for item in raw]
    seen_docker_ids = {s["docker_id"] for s in summaries}

    # 1. Quem sumiu (candidatos a redeploy).
    vanished: list[Container] = [
        c
        for docker_id, c in existing.items()
        if docker_id not in seen_docker_ids and c.state != ContainerState.removed
    ]
    recently_removed: list[Container] = [
        c
        for c in existing.values()
        if c.state == ContainerState.removed and now - c.last_seen_at <= REDEPLOY_WINDOW
    ]
    # Candidato preferido: monitorado e visto mais recentemente. Evita que uma linha antiga
    # com a mesma identidade "roube" o redeploy do projeto em uso.
    redeploy_pool = sorted(
        vanished + recently_removed, key=lambda c: (c.monitored, c.last_seen_at), reverse=True
    )

    # 2. Atualiza presentes, cria novos ou reconhece redeploy. Containers renomeados pelo
    #    Compose são processados primeiro para entrarem no pool antes do substituto.
    summaries.sort(key=lambda s: 0 if COMPOSE_RENAME_RE.match(s["name"]) else 1)
    for s in summaries:
        c = existing.get(s["docker_id"])
        if c is not None and COMPOSE_RENAME_RE.match(s["name"]) and c not in redeploy_pool:
            # Linha existente que está sendo substituída: candidata preferencial.
            redeploy_pool.insert(0, c)
        if c is None:
            if COMPOSE_RENAME_RE.match(s["name"]):
                # Zumbi sem linha própria (a linha migrou para o substituto): não cria nada.
                continue
            match = next(
                (old for old in redeploy_pool if _same_service(_identity(old), _identity(s))), None
            )
            if match is not None:
                redeploy_pool.remove(match)
                if match in vanished:
                    vanished.remove(match)
                prev_image = match.image
                match.docker_id = s["docker_id"]
                existing[s["docker_id"]] = match
                c = match
                result.redeployed.append((c, prev_image, s["image"]))
            else:
                c = Container(
                    id=uuid.uuid4(), host_id=host.id, docker_id=s["docker_id"], first_seen_at=now
                )
                db.add(c)
                result.new.append(c)
        c.name = s["name"]
        c.image = s["image"]
        c.image_digest = s["_raw"].get("ImageID") or None
        c.compose_project = s["compose_project"]
        c.compose_service = s["compose_service"]
        c.labels = s["labels"]
        c.state = _state(s["state"])
        c.last_seen_at = now
        result.present.append(c)

    # 3. Quem sumiu de verdade.
    for c in vanished:
        c.state = ContainerState.removed
        if c.monitored:
            c.monitored = False
            result.removed_monitored.append(c)
        result.removed.append(c)

    await db.flush()

    # 4. Eventos e notificações.
    for c in result.new:
        if result.first_sync:
            # Primeiro inventário do host: os containers aparecem na tela de seleção,
            # não como notificação.
            continue
        db.add(
            HostEvent(
                host_id=host.id,
                type=HostEventType.new_container,
                attributes={"container_id": str(c.id), "name": c.name, "image": c.image},
                occurred_at=now,
            )
        )
        await notify(
            db,
            NotificationType.new_container,
            f"Novo container {c.name} em {host.name}",
            host_id=host.id,
            container_id=c.id,
            payload={"name": c.name, "image": c.image, "state": c.state.value},
        )
    for c in result.removed:
        db.add(
            HostEvent(
                host_id=host.id,
                type=HostEventType.container_removed,
                attributes={"container_id": str(c.id), "name": c.name},
                occurred_at=now,
            )
        )
    for c, prev_image, new_image in result.redeployed:
        db.add(
            DockerEvent(
                container_id=c.id,
                type=DockerEventType.redeploy,
                previous_image=prev_image,
                new_image=new_image,
                attributes={"docker_id": c.docker_id},
                occurred_at=now,
            )
        )
    await db.commit()
    for c in result.present:
        await db.refresh(c)
    if result.new or result.removed or result.redeployed:
        log.info(
            "inventory sync",
            extra={
                "host": host.name,
                "new": [c.name for c in result.new],
                "removed": [c.name for c in result.removed],
                "redeployed": [c.name for c, _, _ in result.redeployed],
                "candidates": len(redeploy_pool) + len(result.redeployed),
                "first_sync": result.first_sync,
            },
        )
    return result


async def record_docker_event(
    db: AsyncSession, host: Host, event: dict[str, Any]
) -> DockerEvent | None:
    """Grava um evento do stream do Docker se for de um container monitorado conhecido."""
    action = str(event.get("Action") or event.get("status") or "")
    base_action = action.split(":", 1)[0].strip()
    actor = event.get("Actor") or {}
    attrs: dict[str, Any] = actor.get("Attributes") or {}
    docker_id = str(actor.get("ID") or event.get("id") or "")
    if not docker_id:
        return None
    if base_action == "health_status":
        type_ = DockerEventType.health_status
    elif base_action in RECORDED_ACTIONS:
        type_ = RECORDED_ACTIONS[base_action]
    else:
        return None
    stmt = select(Container).where(Container.host_id == host.id, Container.docker_id == docker_id)
    container = (await db.execute(stmt)).scalar_one_or_none()
    if container is None or not container.monitored:
        return None
    time_nano = event.get("timeNano")
    occurred_at = (
        datetime.fromtimestamp(int(time_nano) / 1e9, tz=UTC) if time_nano else datetime.now(UTC)
    )
    exit_code: int | None = None
    if "exitCode" in attrs:
        try:
            exit_code = int(attrs["exitCode"])
        except (TypeError, ValueError):
            exit_code = None
    ev = DockerEvent(
        container_id=container.id,
        type=type_,
        exit_code=exit_code,
        attributes={
            "action": action,
            "name": attrs.get("name"),
            "image": attrs.get("image"),
            "signal": attrs.get("signal"),
        },
        occurred_at=occurred_at,
    )
    db.add(ev)
    await db.commit()
    return ev


async def record_host_event(
    db: AsyncSession, host_id: uuid.UUID, type_: HostEventType, **attributes: Any
) -> None:
    db.add(
        HostEvent(host_id=host_id, type=type_, attributes=attributes, occurred_at=datetime.now(UTC))
    )
    await db.commit()


async def list_host_events(
    db: AsyncSession, host_id: uuid.UUID, limit: int = 200
) -> list[HostEvent]:
    stmt = (
        select(HostEvent)
        .where(HostEvent.host_id == host_id)
        .order_by(HostEvent.occurred_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars())


async def list_container_events(
    db: AsyncSession, container_id: uuid.UUID, limit: int = 200
) -> list[DockerEvent]:
    stmt = (
        select(DockerEvent)
        .where(DockerEvent.container_id == container_id)
        .order_by(DockerEvent.occurred_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars())
