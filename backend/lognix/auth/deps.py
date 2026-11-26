"""Dependências FastAPI: usuário atual. Preparado para virar require_role() no futuro."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.auth import service
from lognix.auth.models import User
from lognix.db import get_session
from lognix.errors import ApiError

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def require_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise ApiError(401, "unauthorized", "Autenticação necessária.")
    user = await service.resolve_access_token(db, credentials.credentials)
    if user is None:
        raise ApiError(401, "unauthorized", "Sessão inválida ou expirada.")
    return user


CurrentUser = Annotated[User, Depends(require_user)]


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
