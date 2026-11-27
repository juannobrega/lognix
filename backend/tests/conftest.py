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
from lognix.analysis import manager as manager_module
from lognix.analysis import manual as manual_limit
from lognix.analysis.manager import AnalysisManager
from lognix.auth.routes import login_limiter
from lognix.db import get_engine
from lognix.events import workers as workers_module
from lognix.events.workers import HostWorkers
from lognix.hosts import supervisor as sup_module
from lognix.hosts.supervisor import TunnelSupervisor
from lognix.loki.client import LogLine, LokiClient
from lognix.main import app
from tests.fake_docker import FakeDocker
from tests.fake_ssh import FakeSshBackend

TABLES = [
    "mcp_calls",
    "mcp_keys",
    "ai_calls",
    "insights",
    "ai_models",
    "ai_providers",
    "settings",
    "triggers_fired",
    "analysis_runs",
    "patterns",
    "notifications",
    "docker_events",
    "host_events",
    "alloy_config_versions",
    "containers",
    "tunnel_states",
    "hosts",
    "refresh_tokens",
    "users",
]


def _garante_banco_de_teste() -> None:
    """Cria `lognix_test` se ele não existir, no mesmo Postgres do compose.

    Antes a suíte exigia um segundo contêiner, criado à mão, na mesma porta que o compose usa —
    dois Postgres disputando a 5432, e um passo manual que só se descobre quando os testes
    falham com "database does not exist". Um banco a mais no servidor que já está de pé custa
    nada e tira o passo.
    """
    import psycopg  # type: ignore[import-not-found]

    url = os.environ["DATABASE_URL"]
    alvo = url.rsplit("/", 1)[-1]
    admin = url.replace("+asyncpg", "").rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin, autocommit=True) as conexao:
        existe = conexao.execute("select 1 from pg_database where datname = %s", (alvo,)).fetchone()
        if not existe:
            conexao.execute(f'create database "{alvo}"')


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> None:
    _garante_banco_de_teste()
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
    manual_limit.limpar()
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


class _NoLoki:
    """Loki ausente nos testes que não o configuram: o ciclo registra falha e não avança."""

    async def query_range(self, *a, **k):  # type: ignore[no-untyped-def]
        from lognix.loki.client import LokiError

        raise LokiError("sem Loki no teste")

    async def aclose(self) -> None:
        return None


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
    analysis = AnalysisManager(client_factory=_NoLoki, pause_seconds=3600)
    manager_module.set_analysis_manager(analysis)
    sup_module.set_supervisor(supervisor)
    workers_module.set_host_workers(workers)
    try:
        yield fake, backend, tmp
    finally:
        await analysis.stop()
        manager_module.set_analysis_manager(None)
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


class ScriptedLoki(LokiClient):
    """Devolve linhas fixas para qualquer janela; conta chamadas."""

    lines: list[str] = []
    calls = 0

    def __init__(self) -> None:  # não abre conexão
        self.base_url = "http://loki.test"

    async def aclose(self) -> None:
        return None

    async def query_range(
        self,
        query: str,
        *,
        start_ns: int,
        end_ns: int,
        limit: int = 1000,
        direction: str = "backward",
    ) -> list[LogLine]:
        ScriptedLoki.calls += 1
        base = start_ns
        return [
            LogLine(base + i, line, {"container": "api"})
            for i, line in enumerate(ScriptedLoki.lines)
        ]


@pytest.fixture
async def scripted_loki(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AnalysisManager]:
    ScriptedLoki.lines = []
    ScriptedLoki.calls = 0
    monkeypatch.setattr("lognix.analysis.routes.LokiClient", ScriptedLoki)
    previous = manager_module.get_analysis_manager()
    await previous.stop()
    manager = AnalysisManager(client_factory=ScriptedLoki, pause_seconds=1)
    manager_module.set_analysis_manager(manager)
    try:
        yield manager
    finally:
        await manager.stop()
        manager_module.set_analysis_manager(previous)
