import uuid

import pytest

from lognix.security.crypto import decrypt, encrypt
from lognix.security.passwords import hash_password, verify_password
from lognix.security.tokens import decode_token, issue_access_token, issue_refresh_token


def test_encrypt_roundtrip_and_aad_binding() -> None:
    token = encrypt("segredo", aad="host:1")
    assert decrypt(token, aad="host:1") == "segredo"
    with pytest.raises(Exception):  # noqa: B017
        decrypt(token, aad="host:2")
    assert encrypt("segredo") != encrypt("segredo")  # nonce aleatório


def test_password_hash() -> None:
    h = hash_password("minha-senha-123")
    assert verify_password(h, "minha-senha-123")
    assert not verify_password(h, "outra")
    assert not verify_password("lixo", "minha-senha-123")


def test_tokens_kinds_are_not_interchangeable() -> None:
    uid = uuid.uuid4()
    access, _ = issue_access_token(uid)
    refresh, _ = issue_refresh_token(uid, uuid.uuid4())
    assert decode_token(access, expected_kind="access") is not None
    assert decode_token(access, expected_kind="refresh") is None
    assert decode_token(refresh, expected_kind="refresh") is not None
    assert decode_token("nao-e-um-jwt", expected_kind="access") is None
