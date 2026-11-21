"""Conexão SSH com fixação de fingerprint. Decisão de implementação: asyncssh.

Motivo: suporta chave, chave com passphrase e senha sem binário externo, encaminha
sockets Unix nativamente e permite obter a chave do servidor antes de autenticar,
o que torna a verificação do fingerprint segura: nenhuma credencial é enviada a um
servidor cuja chave não bata com a registrada.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

import asyncssh

from lognix.hosts.models import SshAuthMethod


class SshError(Exception):
    def __init__(self, code: str, message: str, action: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.action = action


class FingerprintMismatchError(SshError):
    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(
            "fingerprint_mismatch",
            f"A chave do servidor mudou. Registrada: {expected}. Atual: {actual}.",
            "Se a mudança for esperada (reinstalação do host), aceite o novo fingerprint "
            "na tela do host. Caso contrário, investigue antes de continuar.",
        )
        self.expected = expected
        self.actual = actual


@dataclass(frozen=True)
class SshCredentials:
    method: SshAuthMethod
    private_key: str | None = None
    key_passphrase: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class SshTarget:
    address: str
    port: int
    user: str


class RemoteConnection(Protocol):
    """O que o túnel e o proxy precisam de uma conexão: abrir um socket Unix remoto e fechar."""

    @property
    def fingerprint(self) -> str: ...

    async def open_unix_connection(
        self, path: str
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]: ...

    def close(self) -> None: ...

    async def wait_closed(self) -> None: ...

    def is_closed(self) -> bool: ...


class SshBackend(Protocol):
    async def fetch_fingerprint(self, target: SshTarget) -> str: ...

    async def connect(
        self, target: SshTarget, creds: SshCredentials, expected_fingerprint: str | None
    ) -> RemoteConnection: ...


class _AsyncsshConnection:
    def __init__(self, conn: asyncssh.SSHClientConnection, fingerprint: str) -> None:
        self._conn = conn
        self._fingerprint = fingerprint

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    async def open_unix_connection(
        self, path: str
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        reader, writer = await self._conn.open_unix_connection(path)
        # asyncssh devolve seus próprios reader/writer; a interface é compatível com asyncio.
        return reader, writer  # type: ignore[return-value]

    def close(self) -> None:
        self._conn.close()

    async def wait_closed(self) -> None:
        await self._conn.wait_closed()

    def is_closed(self) -> bool:
        return self._conn.is_closed()


def _fingerprint_of(key: asyncssh.SSHKey) -> str:
    return key.get_fingerprint("sha256")


class AsyncsshBackend:
    connect_timeout = 15

    async def fetch_fingerprint(self, target: SshTarget) -> str:
        key = await self._server_key(target)
        return _fingerprint_of(key)

    async def _server_key(self, target: SshTarget) -> asyncssh.SSHKey:
        try:
            key = await asyncio.wait_for(
                asyncssh.get_server_host_key(target.address, target.port),
                timeout=self.connect_timeout,
            )
        except TimeoutError as exc:
            raise SshError(
                "unreachable",
                f"Sem resposta de {target.address}:{target.port}.",
                "Verifique endereço, porta e firewall. O Lognix precisa alcançar o host por SSH.",
            ) from exc
        except (OSError, asyncssh.Error) as exc:
            raise SshError(
                "unreachable",
                f"Não foi possível conectar em {target.address}:{target.port}: {exc}",
                "Verifique endereço, porta e firewall. O Lognix precisa alcançar o host por SSH.",
            ) from exc
        if key is None:
            raise SshError(
                "no_host_key", "O servidor não apresentou chave SSH.", "Verifique o serviço SSH."
            )
        return key

    async def connect(
        self, target: SshTarget, creds: SshCredentials, expected_fingerprint: str | None
    ) -> RemoteConnection:
        key = await self._server_key(target)
        actual = _fingerprint_of(key)
        if expected_fingerprint and expected_fingerprint != actual:
            raise FingerprintMismatchError(expected_fingerprint, actual)

        options: dict[str, object] = {
            "username": target.user,
            "known_hosts": ([key], [], []),
            "connect_timeout": self.connect_timeout,
            "keepalive_interval": 15,
            "keepalive_count_max": 3,
        }
        if creds.method == SshAuthMethod.password:
            options["password"] = creds.password
            options["client_keys"] = []
        else:
            try:
                client_key = asyncssh.import_private_key(
                    creds.private_key or "", passphrase=creds.key_passphrase
                )
            except asyncssh.KeyImportError as exc:
                raise SshError(
                    "bad_key",
                    f"Chave privada inválida: {exc}",
                    "Cole a chave privada completa, incluindo as linhas BEGIN e END. "
                    "Se a chave tiver passphrase, escolha o método correspondente.",
                ) from exc
            except asyncssh.KeyEncryptionError as exc:
                raise SshError(
                    "bad_passphrase",
                    "A passphrase da chave está incorreta ou ausente.",
                    "Informe a passphrase correta.",
                ) from exc
            options["client_keys"] = [client_key]
        try:
            conn = await asyncssh.connect(target.address, target.port, **options)
        except asyncssh.PermissionDenied as exc:
            raise SshError(
                "auth_failed",
                f"Autenticação recusada para o usuário {target.user}.",
                "Confira usuário e credencial. Para chave, a chave pública precisa estar em "
                f"~{target.user}/.ssh/authorized_keys no host.",
            ) from exc
        except asyncssh.HostKeyNotVerifiable as exc:
            raise SshError("host_key", f"Chave do host não verificável: {exc}") from exc
        except (OSError, asyncssh.Error, TimeoutError) as exc:
            raise SshError(
                "ssh_failed",
                f"Falha na conexão SSH: {exc}",
                "Verifique o serviço SSH no host e as credenciais.",
            ) from exc
        return _AsyncsshConnection(conn, actual)
