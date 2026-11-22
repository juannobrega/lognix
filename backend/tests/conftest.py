"""Testes de integração contra um Postgres real.

DATABASE_URL aponta para um banco de teste. O esquema é criado via migrações do
Alembic uma vez por sessão e as tabelas são esvaziadas entre testes.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncIterator

import httpx
import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from alembic import command

os.environ.setdefault("LOGNIX_SECRET_KEY", "test-secret-key-with-at-least-32-characters!!")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://lognix:lognix@localhost:5432/lognix_test"
)
os.environ.setdefault("LOGNIX_LOG_LEVEL", "WARNING")
os.environ.setdefault("ALLOY_CONFIG_PATH", "/tmp/lgx-test-alloy/config.alloy")
os.environ.setdefault("TUNNELS_DIR", "/tmp/lgx-test-tunnels")

from lognix.alloy import service as alloy_service
from lognix.auth.routes import login_limiter
from lognix.db import get_engine
from lognix.events import workers as workers_module
from lognix.events.workers import HostWorkers
from lognix.hosts import supervisor as sup_module
from lognix.hosts.supervisor import TunnelSupervisor
from lognix.main import app
from tests.fake_docker import FakeDocker
from tests.fake_ssh import FakeSshBackend

TABLES = [
    "alloy_config_versions",
    "containers",
    "tunnel_states",
    "hosts",
    "refresh_tokens",
    "users",
]


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> None:
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


class FakeAlloy:
    """Captura chamadas de reload. `fail` faz o reload responder 400."""

    def __init__(self) -> None:
        self.reloads = 0
        self.fail = False

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST" and request.url.path == "/-/reload"
            self.reloads += 1
            return (
                httpx.Response(400, text="config invalid")
                if self.fail
                else httpx.Response(200, text="config reloaded")
            )

        return httpx.MockTransport(handler)


@pytest.fixture
def fake_alloy() -> FakeAlloy:
    return alloy_service.get_alloy_manager()._fake  # type: ignore[attr-defined,no-any-return]


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    login_limiter.reset()
    fake = FakeAlloy()
    manager = alloy_service.AlloyManager(
        config_path=os.environ["ALLOY_CONFIG_PATH"],
        alloy_url="http://alloy.test",
        loki_url="http://loki.test:3100",
        tunnels_dir=os.environ["TUNNELS_DIR"],
        transport=fake.transport(),
    )
    manager._fake = fake  # type: ignore[attr-defined]
    alloy_service.set_alloy_manager(manager)
    yield
    alloy_service.set_alloy_manager(None)
    async with get_engine().begin() as conn:
        # Falha rápido em vez de travar a suíte se alguma conexão ficou com transação aberta.
        await conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        for table in TABLES:
            await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client


FIRST_USER = {"email": "admin@example.com", "name": "Admin", "password": "senha-forte-123"}


@pytest.fixture
async def authed(client: AsyncClient) -> AsyncClient:
    resp = await client.post("/api/v1/setup", json=FIRST_USER)
    assert resp.status_code == 201, resp.text
    client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
    return client


_tcp_servers: list[asyncio.base_events.Server] = []


async def open_tcp_port() -> int:
    """Porta TCP local que aceita conexões, para a etapa 1 da validação. Fica aberta até o
    fim do teste (fechada no teardown de fake_env)."""
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    _tcp_servers.append(server)
    return int(server.sockets[0].getsockname()[1])


@pytest.fixture
async def fake_env() -> AsyncIterator[tuple[FakeDocker, FakeSshBackend, str]]:
    tmp = tempfile.mkdtemp(prefix="lgx", dir="/tmp")
    docker_path = os.path.join(tmp, "docker.sock")
    fake = FakeDocker(docker_path)
    await fake.start()
    backend = FakeSshBackend(docker_path)
    supervisor = TunnelSupervisor(backend=backend, tunnels_dir=os.path.join(tmp, "tunnels"))
    workers = HostWorkers(supervisor.socket_path)
    supervisor.on_status = workers.on_host_status
    sup_module.set_supervisor(supervisor)
    workers_module.set_host_workers(workers)
    try:
        yield fake, backend, tmp
    finally:
        await workers.stop()
        await supervisor.stop()
        workers_module.set_host_workers(None)
        sup_module.set_supervisor(None)
        await fake.stop()
        for server in _tcp_servers:
            server.close()
        _tcp_servers.clear()
        # Garante que nenhuma conexão do pool ficou presa por tarefa cancelada.
        await get_engine().dispose()
