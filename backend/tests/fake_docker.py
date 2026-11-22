"""Servidor HTTP mínimo em socket Unix que imita a Docker API, para testes."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from typing import Any

CONTAINERS: list[dict[str, Any]] = [
    {
        "Id": "9c1d" + "0" * 60,
        "Names": ["/api"],
        "Image": "ghcr.io/x/api:1.5.0",
        "ImageID": "sha256:aaaa",
        "State": "running",
        "Status": "Up 2 hours",
        "Labels": {"com.docker.compose.project": "demo", "com.docker.compose.service": "api"},
    },
    {
        "Id": "77ab" + "0" * 60,
        "Names": ["/db"],
        "Image": "postgres:16",
        "ImageID": "sha256:bbbb",
        "State": "exited",
        "Status": "Exited (0)",
        "Labels": {},
    },
]

INSPECT_ENV = [
    "APP_VERSION=1.5.0",
    "DATABASE_URL=postgres://user:secret@db/x",
    "NODE_ENV=production",
]


def _resp(status: int, body: str, ctype: str = "application/json") -> bytes:
    payload = body.encode()
    return (
        f"HTTP/1.1 {status} X\r\nContent-Type: {ctype}\r\nContent-Length: {len(payload)}\r\n\r\n"
    ).encode() + payload


def make_event(action: str, container: dict[str, Any], **attrs: str) -> dict[str, Any]:
    name = container["Names"][0].lstrip("/")
    now = time.time()
    return {
        "Type": "container",
        "Action": action,
        "status": action.split(":")[0],
        "id": container["Id"],
        "Actor": {
            "ID": container["Id"],
            "Attributes": {"name": name, "image": container["Image"], **attrs},
        },
        "time": int(now),
        "timeNano": int(now * 1e9),
    }


class FakeDocker:
    def __init__(self, path: str) -> None:
        self.path = path
        self.requests: list[tuple[str, str]] = []
        self._server: asyncio.base_events.Server | None = None
        self.event_queues: list[asyncio.Queue[dict[str, Any] | None]] = []
        self.events_connections = 0

    async def start(self) -> None:
        if os.path.exists(self.path):
            os.unlink(self.path)
        self._server = await asyncio.start_unix_server(self._handle, path=self.path)

    async def stop(self) -> None:
        for q in self.event_queues:
            q.put_nowait(None)
        assert self._server
        self._server.close()
        await self._server.wait_closed()

    def emit(self, event: dict[str, Any]) -> None:
        """Entrega um evento a todos os streams /events abertos."""
        for q in self.event_queues:
            q.put_nowait(event)

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
                elif path.endswith("/json") and "/containers/" in path:
                    docker_id = path.split("/containers/")[1].split("/")[0]
                    c = next((c for c in CONTAINERS if c["Id"] == docker_id), None)
                    if c is None:
                        w.write(_resp(404, json.dumps({"message": "no such container"})))
                    else:
                        w.write(
                            _resp(
                                200,
                                json.dumps(
                                    {
                                        "Id": c["Id"],
                                        "Image": c.get("ImageID", ""),
                                        "Config": {"Env": INSPECT_ENV},
                                    }
                                ),
                            )
                        )
                elif path.endswith("/events"):
                    self.events_connections += 1
                    q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
                    self.event_queues.append(q)
                    w.write(
                        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
                    )
                    await w.drain()
                    try:
                        while True:
                            ev = await q.get()
                            if ev is None:
                                break
                            chunk = json.dumps(ev).encode() + b"\n"
                            w.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                            await w.drain()
                    finally:
                        with contextlib.suppress(ValueError):
                            self.event_queues.remove(q)
                    w.write(b"0\r\n\r\n")
                    await w.drain()
                    return
                else:
                    # Qualquer coisa que chegue aqui passou pelo proxy indevidamente.
                    w.write(
                        _resp(500, json.dumps({"message": "FAKE DOCKER: should not be reached"}))
                    )
                await w.drain()
        except (asyncio.IncompleteReadError, ConnectionError, asyncio.CancelledError):
            pass
        finally:
            w.close()
