"""Aplicação FastAPI do Lognix."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lognix import __version__
from lognix.api import api_router
from lognix.config import get_settings
from lognix.db import get_engine
from lognix.errors import install_error_handlers
from lognix.logging_setup import setup_logging

log = logging.getLogger("lognix")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.lognix_log_level)
    log.info("lognix starting", extra={"version": __version__})
    yield
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
    install_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
