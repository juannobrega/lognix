"""Agrega os routers de todos os domínios sob /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from lognix.api.health import router as health_router
from lognix.auth.routes import auth_router, setup_router, users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(setup_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
