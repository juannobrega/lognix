"""Aplicação FastAPI do Lognix."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.routing import Route

from lognix import __version__
from lognix.ai.registry import import_legacy_openrouter
from lognix.alloy.service import get_alloy_manager
from lognix.analysis.manager import get_analysis_manager
from lognix.api import api_router
from lognix.api.static import mount_frontend
from lognix.config import get_settings
from lognix.db import get_engine, get_sessionmaker
from lognix.errors import install_error_handlers
from lognix.events.workers import get_host_workers
from lognix.hosts.supervisor import get_supervisor
from lognix.logging_setup import setup_logging
from lognix.mcp.http import app_mcp, rota_exata
from lognix.metrics import metrics_middleware
from lognix.realtime.hub import get_tail_hub
from lognix.realtime.ws import router as ws_router
from lognix.settings import config_file

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
    async with get_sessionmaker()() as db:
        try:
            await import_legacy_openrouter(db)
        except Exception:
            log.exception("import da chave antiga do OpenRouter falhou")
        # Arquivo inválido derruba a subida de propósito: configuração ignorada em silêncio é
        # pior que configuração ausente, porque quem escreveu acredita que ela está valendo.
        await config_file.apply(db, config_file.load(settings.config_file))
    try:
        await get_alloy_manager().apply("inicialização do backend")
    except Exception:
        log.exception("alloy config apply on startup failed")
    recursos = AsyncExitStack()
    # O Mount do Starlette não propaga ciclo de vida: sem isto o gerenciador de sessões do
    # MCP nunca inicia e toda chamada em /mcp morre com "task group is not initialized".
    alvo = app_mcp()
    await recursos.enter_async_context(alvo.router.lifespan_context(alvo))
    yield
    await recursos.aclose()
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
    # O servidor MCP é um app Starlette próprio: montar em vez de embutir mantém o protocolo
    # inteiro sob responsabilidade do SDK. Antes do coringa do frontend, que engoliria /mcp.
    # A rota exata existe porque o Mount casa só /mcp/... e o roteador responderia 307 em /mcp.
    app.router.routes.append(Route("/mcp", endpoint=rota_exata()))
    app.mount("/mcp", app_mcp())
    # Por último: a rota coringa do frontend engoliria as da API se viesse antes.
    mount_frontend(app, Path(get_settings().frontend_dir))
    return app


app = create_app()
