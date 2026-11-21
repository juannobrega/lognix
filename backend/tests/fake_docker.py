"""Servidor HTTP mínimo em socket Unix que imita a Docker API, para testes."""

from __future__ import annotations

import asyncio
import json
import os

CONTAINERS = [
    {
        "Id": "9c1d" + "0" * 60,
        "Names": ["/api"],
        "Image": "ghcr.io/x/api:1.5.0",
        "State": "running",
        "Status": "Up 2 hours",
        "Labels": {"com.docker.compose.project": "demo", "com.docker.compose.service": "api"},
    },
    {
        "Id": "77ab" + "0" * 60,
        "Names": ["/db"],
        "Image": "postgres:16",
        "State": "exited",
        "Status": "Exited (0)",
        "Labels": {},
    },
]


def _resp(status: int, body: str, ctype: str = "application/json") -> bytes:
    payload = body.encode()
    return (
        f"HTTP/1.1 {status} X\r\nContent-Type: {ctype}\r\nContent-Length: {len(payload)}\r\n\r\n"
    ).encode() + payload


class FakeDocker:
    def __init__(self, path: str) -> None:
        self.path = path
        self.requests: list[tuple[str, str]] = []
        self._server: asyncio.base_events.Server | None = None

    async def start(self) -> None:
        if os.path.exists(self.path):
            os.unlink(self.path)
        self._server = await asyncio.start_unix_server(self._handle, path=self.path)

    async def stop(self) -> None:
        assert self._server
        self._server.close()
        await self._server.wait_closed()

    async def _handle(self, r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        try:
            while True:
                head = await r.readuntil(b"\r\n\r\n")
                line = head.split(b"\r\n", 1)[0].decode()
                method, target, _ = line.split(" ")
                self.requests.append((method, target))
                path = target.split("?")[0]
                if path.endswith("/_ping"):
                    w.write(_resp(200, "OK", "text/plain"))
                elif path.endswith("/version"):
                    w.write(_resp(200, json.dumps({"Version": "27.1.1", "ApiVersion": "1.46"})))
                elif path.endswith("/containers/json"):
                    w.write(_resp(200, json.dumps(CONTAINERS)))
                elif path.endswith("/events"):
                    w.write(
                        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
                    )
                    for i in range(3):
                        chunk = (
                            json.dumps({"Type": "container", "Action": "start", "n": i}).encode()
                            + b"\n"
                        )
                        w.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                        await w.drain()
                        await asyncio.sleep(0.05)
                    w.write(b"0\r\n\r\n")
                else:
                    # Qualquer coisa que chegue aqui passou pelo proxy indevidamente.
                    w.write(
                        _resp(500, json.dumps({"message": "FAKE DOCKER: should not be reached"}))
                    )
                await w.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            w.close()
