"""Um túnel: conexão SSH + proxy somente leitura expondo /tunnels/<host_id>.sock."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from datetime import UTC, datetime

from lognix.hosts.readonly_proxy import ReadOnlyProxy
from lognix.hosts.ssh import RemoteConnection, SshBackend, SshCredentials, SshTarget

log = logging.getLogger(__name__)

DOCKER_SOCK = "/var/run/docker.sock"


def socket_path_for(tunnels_dir: str, host_id: uuid.UUID) -> str:
    return os.path.join(tunnels_dir, f"{host_id}.sock")


class Tunnel:
    def __init__(
        self,
        host_id: uuid.UUID,
        host_name: str,
        target: SshTarget,
        creds: SshCredentials,
        expected_fingerprint: str | None,
        backend: SshBackend,
        tunnels_dir: str,
    ) -> None:
        self.host_id = host_id
        self.host_name = host_name
        self.target = target
        self.creds = creds
        self.expected_fingerprint = expected_fingerprint
        self._backend = backend
        self.socket_path = socket_path_for(tunnels_dir, host_id)
        self._conn: RemoteConnection | None = None
        self._proxy: ReadOnlyProxy | None = None
        self.connected_since: datetime | None = None
        self.fingerprint: str | None = None

    @property
    def connected(self) -> bool:
        return self._conn is not None and not self._conn.is_closed()

    async def open(self) -> None:
        conn = await self._backend.connect(self.target, self.creds, self.expected_fingerprint)
        self.fingerprint = conn.fingerprint
        self._conn = conn

        async def open_upstream() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
            if self._conn is None or self._conn.is_closed():
                raise ConnectionError("túnel fechado")
            return await self._conn.open_unix_connection(DOCKER_SOCK)

        proxy = ReadOnlyProxy(self.socket_path, open_upstream, label=self.host_name)
        await proxy.start()
        self._proxy = proxy
        self.connected_since = datetime.now(UTC)
        log.info("tunnel open", extra={"host": self.host_name, "socket": self.socket_path})

    async def close(self) -> None:
        if self._proxy is not None:
            await self._proxy.stop()
            self._proxy = None
        if self._conn is not None:
            self._conn.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._conn.wait_closed(), timeout=5)
            self._conn = None
        self.connected_since = None
