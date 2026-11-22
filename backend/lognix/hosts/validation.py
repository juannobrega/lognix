"""Validação de host em seis etapas, com progresso consultável."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from lognix.docker.client import DockerApiError, DockerClient, summarize_container
from lognix.hosts import credentials
from lognix.hosts.models import Host, HostStatus
from lognix.hosts.ssh import FingerprintMismatchError, SshError, SshTarget
from lognix.hosts.supervisor import TunnelSupervisor
from lognix.hosts.tunnel import DOCKER_SOCK

log = logging.getLogger(__name__)

STEP_NAMES = (
    "Alcançar o host",
    "Autenticar via SSH",
    "Verificar fingerprint do servidor",
    "Encaminhar o socket do Docker",
    "Falar com o Docker",
    "Listar containers",
)


@dataclass
class Step:
    number: int
    name: str
    status: str = "pending"
    message: str | None = None
    action: str | None = None
    detail: str | None = None


@dataclass
class ValidationRun:
    id: uuid.UUID
    host_id: uuid.UUID
    status: str = "running"
    steps: list[Step] = field(
        default_factory=lambda: [Step(i + 1, n) for i, n in enumerate(STEP_NAMES)]
    )
    containers: list[dict[str, Any]] | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    task: asyncio.Task[None] | None = field(default=None, repr=False)

    def step(self, n: int) -> Step:
        return self.steps[n - 1]

    def fail(self, n: int, message: str, action: str | None = None) -> None:
        s = self.step(n)
        s.status, s.message, s.action = "failed", message, action
        self.status = "failed"
        self.finished_at = datetime.now(UTC)


class ValidationRegistry:
    """Guarda as validações recentes em memória. Expira após 1 h."""

    def __init__(self) -> None:
        self._runs: dict[uuid.UUID, ValidationRun] = {}

    def get(self, run_id: uuid.UUID) -> ValidationRun | None:
        self._expire()
        return self._runs.get(run_id)

    def start(self, host: Host, supervisor: TunnelSupervisor) -> ValidationRun:
        run = ValidationRun(id=uuid.uuid4(), host_id=host.id)
        self._runs[run.id] = run
        run.task = asyncio.create_task(_validate(run, host, supervisor), name=f"validate:{host.id}")
        return run

    def _expire(self) -> None:
        cutoff = datetime.now(UTC).timestamp() - 3600
        for key in [k for k, r in self._runs.items() if r.started_at.timestamp() < cutoff]:
            del self._runs[key]


registry = ValidationRegistry()


async def _validate(run: ValidationRun, host: Host, supervisor: TunnelSupervisor) -> None:
    target = SshTarget(host.address, host.ssh_port, host.ssh_user)
    creds = credentials.decrypt_for(host)
    backend = supervisor.backend

    # 1. TCP
    run.step(1).status = "running"
    try:
        await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                None, lambda: socket.create_connection((host.address, host.ssh_port), 10).close()
            ),
            timeout=12,
        )
    except (OSError, TimeoutError) as exc:
        run.fail(
            1,
            f"Sem resposta em {host.address}:{host.ssh_port}: {exc}",
            "Verifique endereço, porta e firewall. O Lognix precisa alcançar o host por SSH.",
        )
        return
    run.step(1).status = "ok"
    run.step(1).detail = f"{host.address}:{host.ssh_port}"

    # 2 e 3. SSH + fingerprint (o backend verifica a chave antes de autenticar)
    run.step(2).status = "running"
    try:
        conn = await backend.connect(target, creds, host.ssh_host_key_fingerprint)
    except FingerprintMismatchError as exc:
        run.step(2).status = "ok"
        run.fail(3, exc.message, exc.action)
        await _mark_fingerprint_error(host.id, host.name, exc.message, supervisor)
        return
    except SshError as exc:
        run.fail(2, exc.message, exc.action)
        return
    run.step(2).status = "ok"
    run.step(2).detail = f"usuário {host.ssh_user}"
    run.step(3).status = "ok"
    run.step(3).detail = conn.fingerprint + (
        " (registrado agora)" if not host.ssh_host_key_fingerprint else ""
    )

    # 4. socket remoto
    run.step(4).status = "running"
    try:
        reader, writer = await asyncio.wait_for(conn.open_unix_connection(DOCKER_SOCK), timeout=10)
        writer.close()
        _ = reader
    except Exception as exc:
        run.fail(
            4,
            f"Não foi possível abrir {DOCKER_SOCK} no host: {exc}",
            "Confirme que o Docker está rodando no host e que o sshd permite encaminhamento: "
            "em /etc/ssh/sshd_config, AllowTcpForwarding e AllowStreamLocalForwarding não podem "
            "estar como 'no'. Após alterar, reinicie o sshd.",
        )
        conn.close()
        return
    finally:
        with contextlib.suppress(Exception):
            conn.close()
    run.step(4).status = "ok"

    # 5. túnel + proxy + /version
    run.step(5).status = "running"
    runner = await supervisor.restart(host)
    try:
        runner = await supervisor.wait_connected(host.id, timeout=30)
    except SshError as exc:
        run.fail(5, exc.message, exc.action)
        return
    client = DockerClient(runner.tunnel.socket_path, timeout=10)
    try:
        try:
            version = await client.version()
        except DockerApiError as exc:
            action = (
                f"O usuário {host.ssh_user} parece não ter acesso ao Docker. No host, execute: "
                f"sudo usermod -aG docker {host.ssh_user} e abra uma nova sessão."
                if exc.status in (None, 403) or "permission" in str(exc).lower()
                else "Verifique o Docker no host."
            )
            run.fail(5, f"O Docker não respondeu pelo túnel: {exc}", action)
            return
        run.step(5).status = "ok"
        run.step(5).detail = f"Docker {version.get('Version', '?')}"

        # 6. containers
        run.step(6).status = "running"
        try:
            raw = await client.containers(all=True)
        except DockerApiError as exc:
            run.fail(6, f"Falha ao listar containers: {exc}")
            return
        run.containers = [summarize_container(c) for c in raw]
        run.step(6).status = "ok"
        run.step(6).detail = f"{len(raw)} containers"
    finally:
        await client.aclose()

    run.status = "ok"
    run.finished_at = datetime.now(UTC)
    await _persist_success(host.id, version.get("Version"), raw)


async def _persist_success(
    host_id: uuid.UUID, docker_version: str | None, raw: list[dict[str, Any]]
) -> None:
    from lognix.containers.service import sync_inventory
    from lognix.db import get_sessionmaker

    async with get_sessionmaker()() as db:
        host = await db.get(Host, host_id)
        if host is None:
            return
        host.docker_version = docker_version
        host.status = HostStatus.connected
        host.last_error = None
        await db.commit()
        _, monitored_changed = await sync_inventory(db, host, raw)
    if monitored_changed:
        from lognix.alloy.service import get_alloy_manager

        await get_alloy_manager().apply(f"host {host.name}: inventário mudou na validação")


async def _mark_fingerprint_error(
    host_id: uuid.UUID, host_name: str, message: str, supervisor: TunnelSupervisor
) -> None:
    """Fingerprint divergente: host em erro, túnel encerrado, notificação para aceite humano."""
    from lognix.db import get_sessionmaker
    from lognix.events.models import HostEventType
    from lognix.events.service import record_host_event
    from lognix.notifications.models import NotificationType
    from lognix.notifications.service import notify

    await supervisor.remove(host_id)
    async with get_sessionmaker()() as db:
        host = await db.get(Host, host_id)
        if host is None:
            return
        host.status = HostStatus.error
        host.last_error = message
        await db.commit()
        await record_host_event(db, host_id, HostEventType.disconnected, error=message)
        await notify(
            db,
            NotificationType.fingerprint_changed,
            f"Fingerprint de {host_name} mudou",
            host_id=host_id,
            payload={"error": message},
        )
        await db.commit()
