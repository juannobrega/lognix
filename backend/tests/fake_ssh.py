"""Backend SSH falso: 'conexão' cujo socket remoto é um FakeDocker local."""

from __future__ import annotations

import asyncio

from lognix.hosts.ssh import FingerprintMismatchError, SshCredentials, SshError, SshTarget

FP = "SHA256:fakefingerprint0000000000000000000000000000"


class FakeConnection:
    def __init__(self, docker_path: str, fingerprint: str = FP) -> None:
        self.docker_path = docker_path
        self._fp = fingerprint
        self._closed = False

    @property
    def fingerprint(self) -> str:
        return self._fp

    async def open_unix_connection(
        self, path: str
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        assert path == "/var/run/docker.sock"
        return await asyncio.open_unix_connection(self.docker_path)

    def close(self) -> None:
        self._closed = True

    async def wait_closed(self) -> None:
        return None

    def is_closed(self) -> bool:
        return self._closed


class FakeSshBackend:
    def __init__(self, docker_path: str) -> None:
        self.docker_path = docker_path
        self.fingerprint = FP
        self.accept_password = "deploy123"
        self.connections: list[FakeConnection] = []

    async def fetch_fingerprint(self, target: SshTarget) -> str:
        return self.fingerprint

    async def connect(
        self, target: SshTarget, creds: SshCredentials, expected_fingerprint: str | None
    ) -> FakeConnection:
        if expected_fingerprint and expected_fingerprint != self.fingerprint:
            raise FingerprintMismatchError(expected_fingerprint, self.fingerprint)
        if creds.method == "password" and creds.password != self.accept_password:
            raise SshError(
                "auth_failed",
                f"Autenticação recusada para o usuário {target.user}.",
                "Confira a senha.",
            )
        if creds.method != "password" and not (creds.private_key or "").startswith("-----BEGIN"):
            raise SshError("bad_key", "Chave privada inválida.", "Cole a chave completa.")
        conn = FakeConnection(self.docker_path, self.fingerprint)
        self.connections.append(conn)
        return conn
