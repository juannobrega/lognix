"""Derivação de chaves a partir de LOGNIX_SECRET_KEY, com contextos distintos."""

from __future__ import annotations

from functools import lru_cache

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from lognix.config import get_settings

_SALT = b"lognix-v1"


def derive_key(context: bytes, length: int = 32) -> bytes:
    secret = get_settings().lognix_secret_key.encode("utf-8")
    hkdf = HKDF(algorithm=hashes.SHA256(), length=length, salt=_SALT, info=context)
    return hkdf.derive(secret)


@lru_cache
def field_key() -> bytes:
    return derive_key(b"fields")


@lru_cache
def jwt_key() -> bytes:
    return derive_key(b"jwt")
