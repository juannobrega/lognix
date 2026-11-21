"""Aplica a config do Alloy: escreve atomicamente, recarrega, versiona, reverte em falha."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass

import httpx
from sqlalchemy import select

from lognix.alloy.generator import render
from lognix.config import get_settings
from lognix.containers.models import AlloyConfigVersion
from lognix.containers.service import monitored_by_host
from lognix.db import get_sessionmaker
from lognix.hosts.tunnel import socket_path_for

log = logging.getLogger(__name__)


@dataclass
class ApplyResult:
    version_id: int | None
    reload_ok: bool
    error: str | None
    hosts_in_config: int
    containers_in_config: int
    content: str


class AlloyManager:
    def __init__(
        self,
        config_path: str | None = None,
        alloy_url: str | None = None,
        loki_url: str | None = None,
        tunnels_dir: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        s = get_settings()
        self.config_path = config_path or s.alloy_config_path
        self.alloy_url = (alloy_url or s.alloy_url).rstrip("/")
        self.loki_url = loki_url or s.loki_url
        self.tunnels_dir = tunnels_dir or s.tunnels_dir
        self._transport = transport
        self._lock_holder: object | None = None

    def current_content(self) -> str | None:
        try:
            with open(self.config_path, encoding="utf-8") as fh:
                return fh.read()
        except FileNotFoundError:
            return None

    async def apply(self, reason: str) -> ApplyResult:
        async with get_sessionmaker()() as db:
            groups = await monitored_by_host(db)
            content = render(
                [(h, cs, socket_path_for(self.tunnels_dir, h.id)) for h, cs in groups],
                self.loki_url,
            )
            n_hosts = len(groups)
            n_containers = sum(len(cs) for _, cs in groups)
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()

            previous = self.current_content()
            self._write_atomic(content)
            ok, error = await self._reload()
            if not ok and previous is not None:
                log.error("alloy reload failed; restoring previous config", extra={"error": error})
                self._write_atomic(previous)
                await self._reload()

            version = AlloyConfigVersion(
                content=content, hash=digest, reason=reason[:255], reload_ok=ok, error=error
            )
            db.add(version)
            await db.commit()
            await db.refresh(version)
            log.info(
                "alloy config applied",
                extra={"reason": reason, "hosts": n_hosts, "containers": n_containers, "ok": ok},
            )
            return ApplyResult(version.id, ok, error, n_hosts, n_containers, content)

    async def versions(self, limit: int = 20) -> list[AlloyConfigVersion]:
        async with get_sessionmaker()() as db:
            stmt = select(AlloyConfigVersion).order_by(AlloyConfigVersion.id.desc()).limit(limit)
            return list((await db.execute(stmt)).scalars())

    def _write_atomic(self, content: str) -> None:
        directory = os.path.dirname(self.config_path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".config-", suffix=".alloy", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.chmod(tmp, 0o644)
            os.replace(tmp, self.config_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    async def _reload(self) -> tuple[bool, str | None]:
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=15) as client:
                resp = await client.post(f"{self.alloy_url}/-/reload")
            if resp.status_code == 200:
                return True, None
            return False, f"HTTP {resp.status_code}: {resp.text[:500]}"
        except httpx.HTTPError as exc:
            return False, f"{type(exc).__name__}: {exc}"


_manager: AlloyManager | None = None


def get_alloy_manager() -> AlloyManager:
    global _manager
    if _manager is None:
        _manager = AlloyManager()
    return _manager


def set_alloy_manager(manager: AlloyManager | None) -> None:
    global _manager
    _manager = manager
