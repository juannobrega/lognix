"""Saúde: versão e estado dos componentes."""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from lognix import __version__
from lognix.config import get_settings
from lognix.db import get_engine

log = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


class ComponentStatus(BaseModel):
    ok: bool
    detail: str | None = None


class Health(BaseModel):
    status: str
    version: str
    components: dict[str, ComponentStatus]


async def check_postgres() -> ComponentStatus:
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("select 1"))
        return ComponentStatus(ok=True)
    except Exception as exc:
        return ComponentStatus(ok=False, detail=type(exc).__name__)


async def check_http(url: str) -> ComponentStatus:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
        return ComponentStatus(ok=resp.status_code == 200, detail=f"HTTP {resp.status_code}")
    except Exception as exc:
        return ComponentStatus(ok=False, detail=type(exc).__name__)


@router.get("", response_model=Health)
async def health() -> Health:
    settings = get_settings()
    postgres, loki, alloy = await asyncio.gather(
        check_postgres(),
        check_http(f"{settings.loki_url}/ready"),
        check_http(f"{settings.alloy_url}/-/ready"),
    )
    components = {"postgres": postgres, "loki": loki, "alloy": alloy}
    # Postgres é obrigatório. Loki e Alloy só entram em uso na fase 0.3.0; até lá
    # são informativos e não derrubam o status.
    status = "ok" if postgres.ok else "degraded"
    return Health(status=status, version=__version__, components=components)
