"""Agrega os routers de todos os domínios sob /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from lognix.analysis.routes import executor_router
from lognix.analysis.routes import insights_router as analysis_insights_router
from lognix.analysis.routes import projects_router as analysis_projects_router
from lognix.api.health import router as health_router
from lognix.api.summary import router as summary_router
from lognix.api.system import router as system_router
from lognix.auth.routes import auth_router, setup_router, users_router
from lognix.containers.logs_routes import router as logs_router
from lognix.containers.routes import hosts_router as containers_hosts_router
from lognix.containers.routes import projects_router
from lognix.events.routes import hosts_router as events_hosts_router
from lognix.events.routes import projects_router as events_projects_router
from lognix.hosts.routes import router as hosts_router
from lognix.notifications.routes import router as notifications_router
from lognix.settings.routes import router as settings_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(setup_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(hosts_router)
api_router.include_router(containers_hosts_router)
api_router.include_router(projects_router)
api_router.include_router(logs_router)
api_router.include_router(events_hosts_router)
api_router.include_router(events_projects_router)
api_router.include_router(notifications_router)
api_router.include_router(analysis_projects_router)
api_router.include_router(analysis_insights_router)
api_router.include_router(executor_router)
api_router.include_router(system_router)
api_router.include_router(summary_router)
api_router.include_router(settings_router)
