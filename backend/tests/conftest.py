"""Testes de integração contra um Postgres real.

DATABASE_URL aponta para um banco de teste. O esquema é criado via migrações do
Alembic uma vez por sessão e as tabelas são esvaziadas entre testes.
"""

from __future__ import annotations

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


@pytest.fixture
async def fake_env() -> AsyncIterator[tuple[FakeDocker, FakeSshBackend, str]]:
    tmp = tempfile.mkdtemp(prefix="lgx", dir="/tmp")
    docker_path = os.path.join(tmp, "docker.sock")
    fake = FakeDocker(docker_path)
    await fake.start()
    backend = FakeSshBackend(docker_path)
    supervisor = TunnelSupervisor(backend=backend, tunnels_dir=os.path.join(tmp, "tunnels"))
    sup_module.set_supervisor(supervisor)
    try:
        yield fake, backend, tmp
    finally:
        await supervisor.stop()
        sup_module.set_supervisor(None)
        await fake.stop()
