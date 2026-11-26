"""JWT de acesso e refresh. HS256 com chave derivada."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from lognix.config import get_settings
from lognix.security.keys import jwt_key

_ALG = "HS256"


@dataclass(frozen=True)
class TokenClaims:
    sub: uuid.UUID
    jti: uuid.UUID
    kind: str
    exp: datetime


def _encode(sub: uuid.UUID, jti: uuid.UUID, kind: str, ttl: int) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    exp = now + timedelta(seconds=ttl)
    payload = {"sub": str(sub), "jti": str(jti), "kind": kind, "iat": now, "exp": exp}
    return jwt.encode(payload, jwt_key(), algorithm=_ALG), exp


def issue_access_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    return _encode(user_id, uuid.uuid4(), "access", get_settings().access_token_ttl_seconds)


def issue_refresh_token(user_id: uuid.UUID, jti: uuid.UUID) -> tuple[str, datetime]:
    return _encode(user_id, jti, "refresh", get_settings().refresh_token_ttl_seconds)


def decode_token(token: str, *, expected_kind: str) -> TokenClaims | None:
    try:
        data = jwt.decode(token, jwt_key(), algorithms=[_ALG])
    except jwt.PyJWTError:
        return None
    if data.get("kind") != expected_kind:
        return None
    try:
        return TokenClaims(
            sub=uuid.UUID(data["sub"]),
            jti=uuid.UUID(data["jti"]),
            kind=str(data["kind"]),
            exp=datetime.fromtimestamp(int(data["exp"]), tz=UTC),
        )
    except (KeyError, ValueError):
        return None
