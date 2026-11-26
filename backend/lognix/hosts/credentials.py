"""Criptografia das credenciais SSH de um host. AAD amarra o campo ao host."""

from __future__ import annotations

from lognix.hosts.models import Host, SshAuthMethod
from lognix.hosts.schemas import HostCredentialsIn
from lognix.hosts.ssh import SshCredentials
from lognix.security.crypto import decrypt, encrypt


def _aad(host: Host, field: str) -> str:
    return f"host:{host.id}:{field}"


def apply(host: Host, creds: HostCredentialsIn) -> None:
    host.ssh_auth_method = creds.ssh_auth_method
    host.ssh_private_key_enc = (
        encrypt(creds.private_key, aad=_aad(host, "key")).encode() if creds.private_key else None
    )
    host.ssh_key_passphrase_enc = (
        encrypt(creds.key_passphrase, aad=_aad(host, "passphrase")).encode()
        if creds.key_passphrase
        else None
    )
    host.ssh_password_enc = (
        encrypt(creds.password, aad=_aad(host, "password")).encode() if creds.password else None
    )


def decrypt_for(host: Host) -> SshCredentials:
    return SshCredentials(
        method=SshAuthMethod(host.ssh_auth_method),
        private_key=decrypt(host.ssh_private_key_enc.decode(), aad=_aad(host, "key"))
        if host.ssh_private_key_enc
        else None,
        key_passphrase=decrypt(host.ssh_key_passphrase_enc.decode(), aad=_aad(host, "passphrase"))
        if host.ssh_key_passphrase_enc
        else None,
        password=decrypt(host.ssh_password_enc.decode(), aad=_aad(host, "password"))
        if host.ssh_password_enc
        else None,
    )
