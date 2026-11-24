"""Aplicação FastAPI do Lognix."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lognix import __version__
from lognix.alloy.service import get_alloy_manager
from lognix.analysis.manager import get_analysis_manager
from lognix.api import api_router
from lognix.config import get_settings
from lognix.db import get_engine
from lognix.errors import install_error_handlers
from lognix.events.workers import get_host_workers
from lognix.hosts.supervisor import get_supervisor
from lognix.logging_setup import setup_logging
from lognix.metrics import metrics_middleware
from lognix.realtime.hub import get_tail_hub
from lognix.realtime.ws import router as ws_router

log = logging.getLogger("lognix")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.lognix_log_level)
    log.info("lognix starting", extra={"version": __version__})
    supervisor = get_supervisor()
    supervisor.on_status = get_host_workers().on_host_status
    await supervisor.start()
    get_tail_hub().start()
    await get_analysis_manager().start()
    try:
        await get_alloy_manager().apply("inicialização do backend")
    except Exception:
        log.exception("alloy config apply on startup failed")
    yield
    await get_analysis_manager().stop()
    await get_tail_hub().stop()
    await get_host_workers().stop()
    await get_supervisor().stop()
    await get_engine().dispose()
    log.info("lognix stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lognix",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.middleware("http")(metrics_middleware)
    install_error_handlers(app)
    app.include_router(api_router)
    app.include_router(ws_router)
    return app


app = create_app()
