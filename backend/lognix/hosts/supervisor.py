"""Supervisor de túneis: um por host, verificação a cada 15 s, reconexão com backoff."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select

from lognix.config import get_settings
from lognix.db import get_sessionmaker
from lognix.docker.client import DockerApiError, DockerClient
from lognix.hosts import credentials
from lognix.hosts.models import Host, HostStatus, TunnelState
from lognix.hosts.ssh import (
    AsyncsshBackend,
    FingerprintMismatchError,
    SshBackend,
    SshError,
    SshTarget,
)
from lognix.hosts.tunnel import Tunnel

log = logging.getLogger(__name__)

CHECK_INTERVAL = 15

StatusListener = Callable[[uuid.UUID, HostStatus | None, HostStatus, str | None], Awaitable[None]]
BACKOFF_START = 2
BACKOFF_MAX = 300


class TunnelRunner:
    """Mantém o túnel de um host vivo enquanto a tarefa existir."""

    def __init__(
        self,
        host: Host,
        backend: SshBackend,
        tunnels_dir: str,
        on_status: StatusListener | None = None,
    ) -> None:
        self.host_id = host.id
        self._on_status = on_status
        self._last_notified: HostStatus | None = None
        self.tunnel = Tunnel(
            host.id,
            host.name,
            SshTarget(host.address, host.ssh_port, host.ssh_user),
            credentials.decrypt_for(host),
            host.ssh_host_key_fingerprint,
            backend,
            tunnels_dir,
        )
        self.attempts = 0
        self.last_error: str | None = None
        self.last_check_at: datetime | None = None
        self.status = HostStatus.pending
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name=f"tunnel:{self.host_id}")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None
        await self.tunnel.close()

    def reconnect_now(self) -> None:
        self._wake.set()

    async def _run(self) -> None:
        backoff = BACKOFF_START
        while True:
            try:
                if not self.tunnel.connected:
                    await self._connect_once()
                    backoff = BACKOFF_START
                await self._check()
                self._wake.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), timeout=CHECK_INTERVAL)
            except asyncio.CancelledError:
                raise
            except FingerprintMismatchError as exc:
                await self._fail(HostStatus.error, exc.message, fatal=True)
                # Não insiste: precisa de aceite humano do novo fingerprint.
                await self._wake.wait()
                self._wake.clear()
                backoff = BACKOFF_START
            except SshError as exc:
                await self._fail(HostStatus.disconnected, exc.message)
                self._wake.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), timeout=backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)
            except Exception as exc:
                log.exception("tunnel runner error", extra={"host_id": str(self.host_id)})
                await self._fail(HostStatus.disconnected, f"{type(exc).__name__}: {exc}")
                self._wake.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), timeout=backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)

    async def _connect_once(self) -> None:
        self.attempts += 1
        await self.tunnel.open()
        self.attempts = 0
        self.last_error = None
        self.status = HostStatus.connected
        await self._persist(fingerprint=self.tunnel.fingerprint)

    async def _check(self) -> None:
        client = DockerClient(self.tunnel.socket_path, timeout=8)
        try:
            await client.ping()
            self.last_check_at = datetime.now(UTC)
            if self.status != HostStatus.connected:
                self.status = HostStatus.connected
                self.last_error = None
            await self._persist()
        except DockerApiError as exc:
            await self.tunnel.close()
            raise SshError("ping_failed", f"Docker não respondeu pelo túnel: {exc}") from exc
        finally:
            await client.aclose()

    async def _fail(self, status: HostStatus, message: str, *, fatal: bool = False) -> None:
        await self.tunnel.close()
        self.status = status
        self.last_error = message
        log.warning(
            "tunnel down",
            extra={"host_id": str(self.host_id), "error": message, "fatal": fatal},
        )
        await self._persist()

    async def _persist(self, *, fingerprint: str | None = None) -> None:
        # Blindado contra cancelamento: uma tarefa cancelada no meio de uma transação deixaria
        # a conexão "idle in transaction" no pool e travaria quem precisasse de lock nas tabelas.
        await asyncio.shield(self._persist_unshielded(fingerprint=fingerprint))

    async def _persist_unshielded(self, *, fingerprint: str | None = None) -> None:
        previous = self._last_notified
        if self._on_status is not None and self.status != previous:
            self._last_notified = self.status
            try:
                await self._on_status(self.host_id, previous, self.status, self.last_error)
            except Exception:
                log.exception("status listener failed", extra={"host_id": str(self.host_id)})
        async with get_sessionmaker()() as db:
            host = await db.get(Host, self.host_id)
            if host is None or host.status == HostStatus.removed:
                return
            host.status = self.status
            host.last_error = self.last_error
            if fingerprint and not host.ssh_host_key_fingerprint:
                host.ssh_host_key_fingerprint = fingerprint
            state = await db.get(TunnelState, self.host_id) or TunnelState(host_id=self.host_id)
            state.socket_path = self.tunnel.socket_path
            state.connected_since = self.tunnel.connected_since
            state.last_check_at = self.last_check_at
            state.reconnect_attempts = self.attempts
            state.last_error = self.last_error
            db.add(state)
            await db.commit()


class TunnelSupervisor:
    def __init__(
        self,
        backend: SshBackend | None = None,
        tunnels_dir: str | None = None,
        on_status: StatusListener | None = None,
    ) -> None:
        self.backend: SshBackend = backend or AsyncsshBackend()
        self.tunnels_dir = tunnels_dir or get_settings().tunnels_dir
        self.on_status = on_status
        self._runners: dict[uuid.UUID, TunnelRunner] = {}

    async def start(self) -> None:
        async with get_sessionmaker()() as db:
            hosts = (
                await db.execute(select(Host).where(Host.status != HostStatus.removed))
            ).scalars()
            for host in hosts:
                self.ensure(host)

    async def stop(self) -> None:
        await asyncio.gather(*(r.stop() for r in self._runners.values()), return_exceptions=True)
        self._runners.clear()

    def ensure(self, host: Host) -> TunnelRunner:
        runner = self._runners.get(host.id)
        if runner is None:
            runner = TunnelRunner(host, self.backend, self.tunnels_dir, self.on_status)
            self._runners[host.id] = runner
            runner.start()
        return runner

    async def restart(self, host: Host) -> TunnelRunner:
        await self.remove(host.id)
        return self.ensure(host)

    async def remove(self, host_id: uuid.UUID, *, removed: bool = False) -> None:
        runner = self._runners.pop(host_id, None)
        if runner is not None:
            await runner.stop()
            if removed and self.on_status is not None:
                with contextlib.suppress(Exception):
                    await self.on_status(host_id, runner.status, HostStatus.removed, None)

    def get(self, host_id: uuid.UUID) -> TunnelRunner | None:
        return self._runners.get(host_id)

    def socket_path(self, host_id: uuid.UUID) -> str | None:
        runner = self._runners.get(host_id)
        if runner is None or not runner.tunnel.connected:
            return None
        return runner.tunnel.socket_path

    async def wait_connected(self, host_id: uuid.UUID, timeout: float = 30) -> TunnelRunner:
        runner = self._runners[host_id]
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if runner.tunnel.connected and runner.status == HostStatus.connected:
                return runner
            if runner.last_error and not runner.tunnel.connected:
                raise SshError("tunnel_failed", runner.last_error)
            await asyncio.sleep(0.2)
        raise SshError("tunnel_timeout", "O túnel não ficou pronto a tempo.")


_supervisor: TunnelSupervisor | None = None


def get_supervisor() -> TunnelSupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = TunnelSupervisor()
    return _supervisor


def set_supervisor(supervisor: TunnelSupervisor | None) -> None:
    global _supervisor
    _supervisor = supervisor
