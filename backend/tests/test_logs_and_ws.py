import asyncio
import json
import socket
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import uvicorn
import websockets
from httpx import AsyncClient

from lognix.loki import client as loki_client_module
from lognix.loki.client import LogLine, LokiClient
from lognix.main import app
from lognix.realtime import hub as hub_module
from lognix.realtime.hub import TailHub
from tests.conftest import FIRST_USER
from tests.fake_docker import FakeDocker
from tests.fake_ssh import FakeSshBackend
from tests.test_containers import _connected_host


class FakeLoki(LokiClient):
    """Loki falso: query_range devolve linhas fixas; tail emite lotes periódicos."""

    calls: list[dict[str, str]] = []

    def __init__(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            FakeLoki.calls.append(dict(request.url.params))
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "result": [
                            {
                                "stream": {"container": "api"},
                                "values": [
                                    ["1700000000000000000", "hello"],
                                    ["1700000001000000000", "world"],
                                ],
                            }
                        ]
                    },
                },
            )

        super().__init__("http://loki.test", transport=httpx.MockTransport(handler))

    async def tail(
        self, query: str, *, start_ns: int | None = None, delay_for: int = 0
    ) -> AsyncIterator[list[LogLine]]:
        for i in range(3):
            await asyncio.sleep(0.05)
            yield [LogLine((start_ns or 0) + i + 1, f"live {i}", {"container": "api"})]
        await asyncio.sleep(10)  # mantém o tail aberto


@pytest.fixture
async def fake_loki(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    FakeLoki.calls.clear()
    monkeypatch.setattr("lognix.containers.logs_routes.LokiClient", FakeLoki)
    hub = TailHub(client_factory=FakeLoki)
    hub_module.set_tail_hub(hub)
    hub.start()
    try:
        yield
    finally:
        await hub.stop()
        hub_module.set_tail_hub(None)
    _ = loki_client_module


async def test_project_logs_endpoint(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_loki: None,
) -> None:
    host_id = await _connected_host(authed)
    inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
    api = next(c for c in inv if c["name"] == "api")

    resp = await authed.get(f"/api/v1/projects/{api['id']}/logs", params={"q": "hel", "limit": 2})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [ln["line"] for ln in body["lines"]] == ["hello", "world"]
    assert body["has_more"] is True
    assert body["query"] == f'{{container_id="{api["id"]}"}} |= "hel"'
    assert FakeLoki.calls[-1]["direction"] == "backward"

    bad = await authed.get(
        f"/api/v1/projects/{api['id']}/logs",
        params={"start": "2026-01-02T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
    )
    assert bad.status_code == 400
    missing = await authed.get(f"/api/v1/projects/{uuid.uuid4()}/logs")
    assert missing.status_code == 404


@pytest.fixture
async def ws_server() -> AsyncIterator[str]:
    """Sobe o app com uvicorn no mesmo loop dos testes (TestClient usaria outro loop e
    quebraria o engine asyncpg). Lifespan desligado: as fixtures já instalam os fakes."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, lifespan="off", log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.02)
    try:
        yield f"ws://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task


async def test_ws_requires_token(ws_server: str) -> None:
    # Sem token o servidor recusa antes do handshake (HTTP 403) ou fecha com 4401.
    with pytest.raises(
        (websockets.exceptions.InvalidStatus, websockets.exceptions.ConnectionClosed)
    ):
        async with websockets.connect(f"{ws_server}/ws") as ws:
            await ws.recv()


async def test_ws_live_logs(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_loki: None,
    ws_server: str,
) -> None:
    host_id = await _connected_host(authed)
    inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
    api = next(c for c in inv if c["name"] == "api")
    token = authed.headers["Authorization"].split(" ", 1)[1]

    received: list[dict] = []  # type: ignore[type-arg]
    async with websockets.connect(f"{ws_server}/ws?token={token}") as ws:
        await ws.send(json.dumps({"type": "subscribe", "channel": f"logs:{api['id']}"}))
        assert json.loads(await ws.recv())["type"] == "subscribed"
        while sum(len(m.get("lines", [])) for m in received) < 3:
            received.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=5)))
        await ws.send(json.dumps({"type": "subscribe", "channel": "logs:not-a-uuid"}))
        received.append(json.loads(await ws.recv()))
        await ws.send(json.dumps({"type": "ping"}))
        received.append(json.loads(await ws.recv()))

    lines = [ln["line"] for m in received if m["type"] == "lines" for ln in m["lines"]]
    assert lines == ["live 0", "live 1", "live 2"]
    assert any(m["type"] == "error" for m in received)
    assert received[-1] == {"type": "pong"}
    _ = FIRST_USER
