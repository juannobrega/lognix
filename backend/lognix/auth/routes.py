"""Rotas: /setup, /auth, /users."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status

from lognix.auth import service
from lognix.auth.deps import CurrentUser, DbSession, client_ip
from lognix.auth.schemas import (
    LoginIn,
    PasswordChangeIn,
    SetupStatus,
    TokenOut,
    UserCreate,
    UserOut,
)
from lognix.auth.service import AuthError, Session
from lognix.config import get_settings
from lognix.errors import ApiError
from lognix.security.rate_limit import RateLimiter

REFRESH_COOKIE = "lognix_refresh"

setup_router = APIRouter(prefix="/setup", tags=["setup"])
auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])

login_limiter = RateLimiter(get_settings().login_rate_limit_per_minute)


def _raise(exc: AuthError, status_code: int) -> None:
    raise ApiError(status_code, exc.code, exc.message) from exc


def _set_refresh_cookie(response: Response, session: Session) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        session.refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings.refresh_token_ttl_seconds,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


def _token_out(session: Session) -> TokenOut:
    return TokenOut(
        access_token=session.access_token,
        expires_at=session.access_expires_at,
        user=UserOut.model_validate(session.user),
    )


# ---- setup -----------------------------------------------------------------


@setup_router.get("/status", response_model=SetupStatus)
async def setup_status(db: DbSession) -> SetupStatus:
    return SetupStatus(needs_setup=await service.count_users(db) == 0)


@setup_router.post("", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def setup(body: UserCreate, db: DbSession, response: Response) -> TokenOut:
    if await service.count_users(db) > 0:
        raise ApiError(404, "not_found", "Configuração inicial já realizada.")
    try:
        await service.create_user(db, email=body.email, name=body.name, password=body.password)
        session = await service.login(db, email=body.email, password=body.password)
    except AuthError as exc:
        _raise(exc, 400)
        raise  # pragma: no cover
    _set_refresh_cookie(response, session)
    return _token_out(session)


# ---- auth ------------------------------------------------------------------


@auth_router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, db: DbSession, response: Response) -> TokenOut:
    if not login_limiter.allow(client_ip(request)):
        raise ApiError(
            429,
            "rate_limited",
            "Muitas tentativas de login.",
            "Aguarde um minuto e tente novamente.",
        )
    try:
        session = await service.login(db, email=body.email, password=body.password)
    except AuthError as exc:
        _raise(exc, 401)
        raise  # pragma: no cover
    _set_refresh_cookie(response, session)
    return _token_out(session)


@auth_router.post("/refresh", response_model=TokenOut)
async def refresh(
    db: DbSession,
    response: Response,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenOut:
    if not refresh_cookie:
        raise ApiError(401, "invalid_refresh", "Sessão ausente. Entre novamente.")
    try:
        session = await service.refresh(db, refresh_cookie)
    except AuthError as exc:
        _clear_refresh_cookie(response)
        _raise(exc, 401)
        raise  # pragma: no cover
    _set_refresh_cookie(response, session)
    return _token_out(session)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    db: DbSession,
    response: Response,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> None:
    await service.logout(db, refresh_cookie)
    _clear_refresh_cookie(response)


@auth_router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


# ---- users -----------------------------------------------------------------


@users_router.get("", response_model=list[UserOut])
async def list_users(_: CurrentUser, db: DbSession) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in await service.list_users(db)]


@users_router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, _: CurrentUser, db: DbSession) -> UserOut:
    try:
        user = await service.create_user(
            db, email=body.email, name=body.name, password=body.password
        )
    except AuthError as exc:
        _raise(exc, 409)
        raise  # pragma: no cover
    return UserOut.model_validate(user)


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, _: CurrentUser, db: DbSession) -> None:
    try:
        await service.delete_user(db, user_id)
    except AuthError as exc:
        _raise(exc, 404 if exc.code == "not_found" else 409)


@users_router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: PasswordChangeIn, user: CurrentUser, db: DbSession, response: Response
) -> None:
    try:
        await service.change_password(
            db, user, current_password=body.current_password, new_password=body.new_password
        )
    except AuthError as exc:
        _raise(exc, 400)
    _clear_refresh_cookie(response)
