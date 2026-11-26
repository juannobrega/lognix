"""Criptografia autenticada de campos (AES-256-GCM). Formato: base64(nonce || ciphertext)."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from lognix.security.keys import field_key

_NONCE_LEN = 12


def encrypt(plaintext: str, *, aad: str = "") -> str:
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = AESGCM(field_key()).encrypt(nonce, plaintext.encode("utf-8"), aad.encode("utf-8"))
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt(token: str, *, aad: str = "") -> str:
    raw = base64.b64decode(token.encode("ascii"))
    nonce, ciphertext = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
    plaintext = AESGCM(field_key()).decrypt(nonce, ciphertext, aad.encode("utf-8"))
    return plaintext.decode("utf-8")
