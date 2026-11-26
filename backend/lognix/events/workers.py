"""Workers por host: ouvinte de eventos Docker e reconciliação periódica do inventário.

Iniciados quando o túnel do host conecta, parados quando desconecta ou o host é removido.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar

from sqlalchemy import select

from lognix.alloy.service import get_alloy_manager
from lognix.containers.models import Container
from lognix.db import get_sessionmaker
from lognix.docker.client import DockerApiError, DockerClient, summarize_env
from lognix.events import service
from lognix.events.models import HostEventType
from lognix.hosts.models import Host, HostStatus
from lognix.metrics import (
    docker_events_total,
    events_stream_restarts_total,
    inventory_sync_duration,
)
from lognix.notifications.models import Notification, NotificationStatus, NotificationType
from lognix.notifications.service import notify

log = logging.getLogger(__name__)

RECONCILE_INTERVAL = 60
T = TypeVar("T")
INVENTORY_ACTIONS = {"start", "destroy", "die", "create", "rename"}
SocketResolver = Callable[[uuid.UUID], str | None]


class HostWorker:
    def __init__(self, host_id: uuid.UUID, socket_for: SocketResolver) -> None:
        self.host_id = host_id
        self._socket_for = socket_for
        self._listener: asyncio.Task[None] | None = None
        self._reconciler: asyncio.Task[None] | None = None
        self._sync_now = asyncio.Event()
        self.last_event_time: int | None = None
        self.events_seen = 0
        self.stream_restarts = 0
        self.last_sync_at: float | None = None
        self.last_error: str | None = None
        self._inflight: set[asyncio.Future[Any]] = set()

    def start(self) -> None:
        if self._listener is None:
            self._listener = asyncio.create_task(self._listen(), name=f"events:{self.host_id}")
        if self._reconciler is None:
            self._reconciler = asyncio.create_task(
                self._reconcile_loop(), name=f"reconcile:{self.host_id}"
            )

    async def stop(self) -> None:
        for task in (self._listener, self._reconciler):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    # Fechar um stream HTTP cancelado pode demorar; não trava quem chamou.
                    await asyncio.wait_for(task, timeout=5)
        self._listener = self._reconciler = None
        for fut in list(self._inflight):
            if not fut.done():
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await asyncio.wait_for(asyncio.shield(fut), timeout=30)

    def _track(self, coro: Coroutine[Any, Any, T]) -> asyncio.Future[T]:
        fut: asyncio.Future[T] = asyncio.ensure_future(coro)
        self._inflight.add(fut)
        fut.add_done_callback(self._inflight.discard)
        return fut

    def request_sync(self) -> None:
        self._sync_now.set()

    # ---- reconciliação ------------------------------------------------------

    async def _reconcile_loop(self) -> None:
        while True:
            # Limpa ANTES de sincronizar: um pedido que chegue durante a sincronização
            # (ex.: `start` logo após `destroy` num redeploy) dispara a próxima rodada.
            self._sync_now.clear()
            try:
                await asyncio.shield(self._track(self.sync_once()))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.warning(
                    "reconcile failed", extra={"host_id": str(self.host_id), "error": str(exc)}
                )
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._sync_now.wait(), timeout=RECONCILE_INTERVAL)

    async def sync_once(self) -> service.SyncResult | None:
        socket_path = self._socket_for(self.host_id)
        if socket_path is None:
            return None
        started = time.monotonic()
        client = DockerClient(socket_path)
        try:
            raw = await client.containers(all=True)
            async with get_sessionmaker()() as db:
                host = await db.get(Host, self.host_id)
                if host is None or host.status == HostStatus.removed:
                    return None
                result = await service.sync_inventory(db, host, raw)
                host_name = host.name
                # Inspeção dos monitorados: variáveis só por nome.
                for c in result.present:
                    if c.monitored and not c.env:
                        await self._inspect(client, db, c)
            self.last_sync_at = time.monotonic()
            if result.monitored_changed:
                reasons = [f"redeploy de {c.name}" for c, _, _ in result.redeployed if c.monitored]
                reasons += [f"{c.name} removido" for c in result.removed if c.monitored]
                await get_alloy_manager().apply(f"host {host_name}: " + ", ".join(reasons))
            return result
        except DockerApiError as exc:
            self.last_error = str(exc)
            return None
        finally:
            inventory_sync_duration.observe(time.monotonic() - started)
            await client.aclose()

    async def _inspect(self, client: DockerClient, db, c: Container) -> None:  # type: ignore[no-untyped-def]
        try:
            data = await client.inspect(c.docker_id)
        except DockerApiError:
            return
        c.env = summarize_env(data)
        image_id = (data.get("Image") or "").strip()
        if image_id:
            c.image_digest = image_id
        await db.commit()

    # ---- eventos ------------------------------------------------------------

    async def _listen(self) -> None:
        backoff = 1.0
        while True:
            socket_path = self._socket_for(self.host_id)
            if socket_path is None:
                await asyncio.sleep(2)
                continue
            client = DockerClient(socket_path)
            try:
                since = (self.last_event_time + 1) if self.last_event_time else None
                async for event in client.events(since=since):
                    await self._handle(event)
                    backoff = 1.0
                # Stream terminou sem erro: reabre a partir do último evento.
                self.stream_restarts += 1
                events_stream_restarts_total.inc()
            except asyncio.CancelledError:
                raise
            except DockerApiError as exc:
                self.last_error = str(exc)
                self.stream_restarts += 1
                events_stream_restarts_total.inc()
                log.warning(
                    "events stream error", extra={"host_id": str(self.host_id), "error": str(exc)}
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.exception("events listener crashed", extra={"host_id": str(self.host_id)})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            finally:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(client.aclose(), timeout=2)

    async def _handle(self, event: dict) -> None:  # type: ignore[type-arg]
        self.events_seen += 1
        docker_events_total.labels(
            str(event.get("Action") or event.get("status") or "unknown").split(":", 1)[0]
        ).inc()
        if event.get("time"):
            self.last_event_time = int(event["time"])
        action = str(event.get("Action") or event.get("status") or "").split(":", 1)[0]
        await asyncio.shield(self._track(self._record(event)))
        if action in INVENTORY_ACTIONS:
            self.request_sync()

    async def _record(self, event: dict) -> None:  # type: ignore[type-arg]
        async with get_sessionmaker()() as db:
            host = await db.get(Host, self.host_id)
            if host is None or host.status == HostStatus.removed:
                return
            await service.record_docker_event(db, host, event)


class HostWorkers:
    def __init__(self, socket_for: SocketResolver) -> None:
        self._socket_for = socket_for
        self._workers: dict[uuid.UUID, HostWorker] = {}
        self._stopping: set[asyncio.Task[None]] = set()

    def ensure(self, host_id: uuid.UUID) -> HostWorker:
        worker = self._workers.get(host_id)
        if worker is None:
            worker = HostWorker(host_id, self._socket_for)
            self._workers[host_id] = worker
            worker.start()
        return worker

    async def remove(self, host_id: uuid.UUID) -> None:
        worker = self._workers.pop(host_id, None)
        if worker is not None:
            await worker.stop()

    def get(self, host_id: uuid.UUID) -> HostWorker | None:
        return self._workers.get(host_id)

    async def stop(self) -> None:
        await asyncio.gather(*(w.stop() for w in self._workers.values()), return_exceptions=True)
        self._workers.clear()

    async def on_host_status(
        self, host_id: uuid.UUID, old: HostStatus | None, new: HostStatus, error: str | None
    ) -> None:
        """Reage às transições do túnel: eventos de host, notificações, workers."""
        async with get_sessionmaker()() as db:
            host = await db.get(Host, host_id)
            if host is None:
                return
            name = host.name
            if new == HostStatus.connected and old != HostStatus.connected:
                await service.record_host_event(db, host_id, HostEventType.connected)
                pending = await db.execute(
                    select(Notification).where(
                        Notification.host_id == host_id,
                        Notification.status == NotificationStatus.new,
                        Notification.type.in_(
                            [
                                NotificationType.host_disconnected,
                                NotificationType.fingerprint_changed,
                            ]
                        ),
                    )
                )
                if old in (HostStatus.disconnected, HostStatus.error) or pending.scalars().first():
                    await notify(
                        db,
                        NotificationType.host_reconnected,
                        f"{name} reconectado",
                        host_id=host_id,
                        dedupe=False,
                    )
                    await db.commit()
            elif new in (HostStatus.disconnected, HostStatus.error) and old == HostStatus.connected:
                await service.record_host_event(
                    db, host_id, HostEventType.disconnected, error=error or ""
                )
                type_ = (
                    NotificationType.fingerprint_changed
                    if error and "chave do servidor mudou" in error
                    else NotificationType.host_disconnected
                )
                title = (
                    f"Fingerprint de {name} mudou"
                    if type_ == NotificationType.fingerprint_changed
                    else f"{name} desconectado"
                )
                await notify(db, type_, title, host_id=host_id, payload={"error": error or ""})
                await db.commit()
        if new == HostStatus.connected:
            self.ensure(host_id).request_sync()
        else:
            # Parar workers pode levar alguns segundos (stream HTTP); não segura o chamador.
            worker = self._workers.pop(host_id, None)
            if worker is not None:
                task = asyncio.create_task(worker.stop(), name=f"stop-workers:{host_id}")
                self._stopping.add(task)
                task.add_done_callback(self._stopping.discard)


_workers: HostWorkers | None = None


def get_host_workers() -> HostWorkers:
    global _workers
    if _workers is None:
        from lognix.hosts.supervisor import get_supervisor

        _workers = HostWorkers(get_supervisor().socket_path)
    return _workers


def set_host_workers(workers: HostWorkers | None) -> None:
    global _workers
    _workers = workers


StatusListener = Callable[[uuid.UUID, HostStatus | None, HostStatus, str | None], Awaitable[None]]
