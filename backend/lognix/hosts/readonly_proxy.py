"""Proxy somente leitura para a Docker API, sobre socket Unix.

Único caminho entre o Lognix (Alloy e backend) e o Docker de um host. Só repassa
requisições GET cujo caminho esteja na lista do ADR 003. Tudo o mais recebe 403 e
é registrado. Conexões persistentes são suportadas: cada requisição é inspecionada.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

log = logging.getLogger(__name__)
audit = logging.getLogger("lognix.audit.docker_proxy")

# Caminhos permitidos (ADR 003). Prefixo opcional de versão da API: /v1.47/...
_VERSION = r"(?:/v\d+\.\d+)?"
ALLOWED_PATHS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"^{_VERSION}{p}(?:\?.*)?$")
    for p in (
        r"/_ping",
        r"/version",
        r"/info",
        r"/containers/json",
        r"/containers/[A-Za-z0-9_.-]+/json",
        r"/containers/[A-Za-z0-9_.-]+/logs",
        r"/events",
        r"/images/[A-Za-z0-9_.:/@-]+/json",
    )
)
ALLOWED_METHODS = frozenset({"GET", "HEAD"})

OpenUpstream = Callable[[], Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]]

_MAX_HEAD = 64 * 1024


class RequestRejectedError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass
class ParsedRequest:
    method: str
    target: str
    raw_head: bytes
    content_length: int = 0
    chunked: bool = False
    close_after: bool = False
    headers: dict[str, str] = field(default_factory=dict)


def parse_head(head: bytes) -> ParsedRequest:
    try:
        text = head.decode("latin-1")
    except UnicodeDecodeError as exc:
        raise RequestRejectedError(400, "cabeçalho inválido") from exc
    lines = text.split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) != 3 or not parts[2].startswith("HTTP/1."):
        raise RequestRejectedError(400, "linha de requisição inválida")
    method, target, version = parts
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
    req = ParsedRequest(method=method.upper(), target=target, raw_head=head, headers=headers)
    if "content-length" in headers:
        try:
            req.content_length = int(headers["content-length"])
        except ValueError as exc:
            raise RequestRejectedError(400, "content-length inválido") from exc
    if "chunked" in headers.get("transfer-encoding", "").lower():
        req.chunked = True
    conn = headers.get("connection", "").lower()
    req.close_after = "close" in conn or version == "HTTP/1.0"
    return req


def is_allowed(method: str, target: str) -> bool:
    if method not in ALLOWED_METHODS:
        return False
    path = target.split("#", 1)[0]
    return any(p.match(path) for p in ALLOWED_PATHS)


def _response(status: int, reason: str, body: str) -> bytes:
    payload = body.encode("utf-8")
    return (
        f"HTTP/1.1 {status} {reason}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii") + payload


class ReadOnlyProxy:
    def __init__(self, listen_path: str, open_upstream: OpenUpstream, *, label: str = "") -> None:
        self.listen_path = listen_path
        self._open_upstream = open_upstream
        self.label = label or listen_path
        self._server: asyncio.base_events.Server | None = None
        self.rejected_count = 0

    async def start(self) -> None:
        directory = os.path.dirname(self.listen_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if os.path.exists(self.listen_path):
            os.unlink(self.listen_path)
        self._server = await asyncio.start_unix_server(self._handle, path=self.listen_path)
        os.chmod(self.listen_path, 0o660)
        log.info("readonly proxy listening", extra={"socket": self.listen_path, "host": self.label})

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if os.path.exists(self.listen_path):
            os.unlink(self.listen_path)

    async def _handle(self, client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
        upstream: tuple[asyncio.StreamReader, asyncio.StreamWriter] | None = None
        pump: asyncio.Task[None] | None = None
        try:
            while True:
                try:
                    head = await client_r.readuntil(b"\r\n\r\n")
                except asyncio.IncompleteReadError:
                    return
                except asyncio.LimitOverrunError:
                    client_w.write(_response(431, "Request Header Fields Too Large", "{}"))
                    return
                if len(head) > _MAX_HEAD:
                    client_w.write(_response(431, "Request Header Fields Too Large", "{}"))
                    return
                try:
                    req = parse_head(head)
                except RequestRejectedError as exc:
                    client_w.write(
                        _response(exc.status, "Bad Request", f'{{"message":"{exc.reason}"}}')
                    )
                    return
                if not is_allowed(req.method, req.target):
                    self.rejected_count += 1
                    audit.warning(
                        "docker api request rejected",
                        extra={"host": self.label, "method": req.method, "target": req.target},
                    )
                    client_w.write(
                        _response(
                            403,
                            "Forbidden",
                            '{"message":"Lognix: somente leitura. '
                            'Esta requisição não é permitida."}',
                        )
                    )
                    return
                if req.chunked:
                    client_w.write(_response(411, "Length Required", "{}"))
                    return

                if upstream is None:
                    upstream = await self._open_upstream()
                    pump = asyncio.create_task(_pump(upstream[0], client_w))
                up_r, up_w = upstream
                up_w.write(req.raw_head)
                if req.content_length:
                    up_w.write(await client_r.readexactly(req.content_length))
                await up_w.drain()
                if req.close_after:
                    if pump is not None:
                        await pump
                    return
                # Próxima requisição na mesma conexão, enquanto a resposta flui pelo pump.
                _ = up_r
        except (ConnectionError, asyncio.CancelledError, OSError) as exc:
            log.debug("proxy connection ended", extra={"host": self.label, "reason": repr(exc)})
        finally:
            if pump is not None and not pump.done():
                pump.cancel()
            if upstream is not None:
                upstream[1].close()
            with contextlib.suppress(Exception):
                await client_w.drain()
            client_w.close()


async def _pump(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await src.read(64 * 1024)
            if not chunk:
                break
            dst.write(chunk)
            await dst.drain()
    except (ConnectionError, asyncio.CancelledError, OSError) as exc:
        log.debug("proxy pump ended", extra={"reason": repr(exc)})
    finally:
        with contextlib.suppress(Exception):
            dst.write_eof()
