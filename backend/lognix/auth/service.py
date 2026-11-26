"""Regras de usuários e sessões. Sem FastAPI aqui: só banco e segurança."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.auth.models import RefreshToken, User
from lognix.security.passwords import hash_password, verify_password
from lognix.security.tokens import decode_token, issue_access_token, issue_refresh_token


@dataclass(frozen=True)
class Session:
    user: User
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


class AuthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def count_users(db: AsyncSession) -> int:
    return int((await db.execute(select(func.count()).select_from(User))).scalar_one())


async def list_users(db: AsyncSession) -> list[User]:
    return list((await db.execute(select(User).order_by(User.created_at))).scalars())


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(func.lower(User.email) == email.lower())
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_user(db: AsyncSession, *, email: str, name: str, password: str) -> User:
    if await get_user_by_email(db, email):
        raise AuthError("email_taken", "Já existe um usuário com este e-mail.")
    user = User(email=email.lower(), name=name, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await get_user(db, user_id)
    if user is None:
        raise AuthError("not_found", "Usuário não encontrado.")
    if await count_users(db) <= 1:
        raise AuthError("last_user", "Não é possível remover o último usuário.")
    await db.delete(user)
    await db.commit()


async def change_password(
    db: AsyncSession, user: User, *, current_password: str, new_password: str
) -> None:
    if not verify_password(user.password_hash, current_password):
        raise AuthError("wrong_password", "Senha atual incorreta.")
    user.password_hash = hash_password(new_password)
    await _revoke_all(db, user.id)
    await db.commit()


async def _start_session(db: AsyncSession, user: User, family_id: uuid.UUID) -> Session:
    jti = uuid.uuid4()
    refresh, refresh_exp = issue_refresh_token(user.id, jti)
    db.add(RefreshToken(jti=jti, user_id=user.id, family_id=family_id, expires_at=refresh_exp))
    await db.commit()
    access, access_exp = issue_access_token(user.id)
    return Session(user, access, access_exp, refresh, refresh_exp)


async def login(db: AsyncSession, *, email: str, password: str) -> Session:
    user = await get_user_by_email(db, email)
    # Mesma resposta para usuário inexistente e senha errada.
    if user is None or not verify_password(user.password_hash, password):
        raise AuthError("invalid_credentials", "E-mail ou senha incorretos.")
    return await _start_session(db, user, uuid.uuid4())


async def refresh(db: AsyncSession, refresh_token: str) -> Session:
    claims = decode_token(refresh_token, expected_kind="refresh")
    if claims is None:
        raise AuthError("invalid_refresh", "Sessão inválida. Entre novamente.")
    stored = await db.get(RefreshToken, claims.jti)
    if stored is None:
        raise AuthError("invalid_refresh", "Sessão inválida. Entre novamente.")
    now = datetime.now(UTC)
    if stored.revoked_at is not None:
        # Reuso de token já rotacionado: sinal de roubo. Derruba a família inteira.
        await _revoke_family(db, stored.family_id)
        await db.commit()
        raise AuthError("refresh_reused", "Sessão revogada por segurança. Entre novamente.")
    if stored.expires_at <= now:
        raise AuthError("invalid_refresh", "Sessão expirada. Entre novamente.")
    user = await get_user(db, stored.user_id)
    if user is None:
        raise AuthError("invalid_refresh", "Sessão inválida. Entre novamente.")
    stored.revoked_at = now
    return await _start_session(db, user, stored.family_id)


async def logout(db: AsyncSession, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    claims = decode_token(refresh_token, expected_kind="refresh")
    if claims is None:
        return
    stored = await db.get(RefreshToken, claims.jti)
    if stored is not None:
        await _revoke_family(db, stored.family_id)
        await db.commit()


async def _revoke_family(db: AsyncSession, family_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def _revoke_all(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def resolve_access_token(db: AsyncSession, token: str) -> User | None:
    claims = decode_token(token, expected_kind="access")
    if claims is None:
        return None
    return await get_user(db, claims.sub)
