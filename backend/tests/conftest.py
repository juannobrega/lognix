"""Testes de integração contra um Postgres real.

DATABASE_URL aponta para um banco de teste. O esquema é criado via migrações do
Alembic uma vez por sessão e as tabelas são esvaziadas entre testes.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

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

from lognix.auth.routes import login_limiter
from lognix.db import get_engine
from lognix.main import app

TABLES = ["tunnel_states", "hosts", "refresh_tokens", "users"]


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> None:
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    login_limiter.reset()
    yield
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
