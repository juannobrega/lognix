"""Agrega os routers de todos os domínios sob /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from lognix.api.health import router as health_router
from lognix.auth.routes import auth_router, setup_router, users_router
from lognix.containers.logs_routes import router as logs_router
from lognix.containers.routes import hosts_router as containers_hosts_router
from lognix.containers.routes import projects_router
from lognix.hosts.routes import router as hosts_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(setup_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(hosts_router)
api_router.include_router(containers_hosts_router)
api_router.include_router(projects_router)
api_router.include_router(logs_router)
