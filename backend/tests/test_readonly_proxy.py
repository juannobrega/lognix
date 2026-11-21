import asyncio
import os
import tempfile

import httpx
import pytest

from lognix.hosts.readonly_proxy import ReadOnlyProxy, is_allowed
from tests.fake_docker import FakeDocker


@pytest.mark.parametrize(
    ("method", "target", "ok"),
    [
        ("GET", "/_ping", True),
        ("GET", "/v1.47/version", True),
        ("GET", "/containers/json?all=1", True),
        ("GET", "/containers/abc123/logs?follow=1&stdout=1", True),
        ("GET", "/containers/abc123/json", True),
        ("GET", "/events?filters=%7B%22type%22%3A%5B%22container%22%5D%7D", True),
        ("GET", "/images/sha256:abc/json", True),
        ("GET", "/networks", True),
        ("GET", "/v1.47/networks?filters=%7B%7D", True),
        ("GET", "/networks/bridge", True),
        ("POST", "/networks/create", False),
        ("DELETE", "/networks/bridge", False),
        ("POST", "/networks/bridge/connect", False),
        ("POST", "/containers/abc123/restart", False),
        ("POST", "/containers/create", False),
        ("DELETE", "/containers/abc123", False),
        ("POST", "/containers/abc123/exec", False),
        ("GET", "/containers/abc123/attach", False),
        ("GET", "/containers/abc123/export", False),
        ("GET", "/volumes", False),
        ("GET", "/containers/../../_ping", False),
        ("PUT", "/_ping", False),
    ],
)
def test_allowlist(method: str, target: str, ok: bool) -> None:
    assert is_allowed(method, target) is ok


@pytest.fixture
async def proxied() -> tuple[FakeDocker, str]:  # type: ignore[misc]
    tmp = tempfile.mkdtemp(prefix="lgx", dir="/tmp")
    docker_path = os.path.join(tmp, "docker.sock")
    proxy_path = os.path.join(tmp, "proxy.sock")
    fake = FakeDocker(docker_path)
    await fake.start()

    async def upstream() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return await asyncio.open_unix_connection(docker_path)

    proxy = ReadOnlyProxy(proxy_path, upstream, label="test")
    await proxy.start()
    try:
        yield fake, proxy_path
    finally:
        await proxy.stop()
        await fake.stop()


async def test_proxy_passes_get_and_blocks_mutations(proxied: tuple[FakeDocker, str]) -> None:
    fake, proxy_path = proxied
    async with httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(uds=proxy_path), base_url="http://d"
    ) as c:
        assert (await c.get("/_ping")).text == "OK"
        assert (await c.get("/version")).json()["Version"] == "27.1.1"
        assert len((await c.get("/containers/json", params={"all": "true"})).json()) == 2

        for method, path in [
            ("POST", "/containers/9c1d/restart"),
            ("POST", "/containers/9c1d/kill"),
            ("DELETE", "/containers/9c1d"),
            ("POST", "/containers/create"),
            ("POST", "/containers/9c1d/exec"),
            ("GET", "/containers/9c1d/attach"),
        ]:
            resp = await c.request(method, path)
            assert resp.status_code == 403, (method, path, resp.status_code)
            assert "somente leitura" in resp.text

    # Nada além de GET permitido chegou ao Docker falso.
    assert all(m == "GET" for m, _ in fake.requests)
    assert all(
        t.split("?")[0] in {"/_ping", "/version", "/containers/json"} for _, t in fake.requests
    )


async def test_proxy_streams_chunked_responses(proxied: tuple[FakeDocker, str]) -> None:
    _, proxy_path = proxied
    async with httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(uds=proxy_path), base_url="http://d", timeout=5
    ) as c:
        lines = []
        async with c.stream("GET", "/events") as resp:
            async for line in resp.aiter_lines():
                if line:
                    lines.append(line)
        assert len(lines) == 3


async def test_proxy_keepalive_multiple_requests_one_connection(
    proxied: tuple[FakeDocker, str],
) -> None:
    _, proxy_path = proxied
    reader, writer = await asyncio.open_unix_connection(proxy_path)
    for _ in range(3):
        writer.write(b"GET /_ping HTTP/1.1\r\nHost: d\r\n\r\n")
        await writer.drain()
        head = await reader.readuntil(b"\r\n\r\n")
        assert head.startswith(b"HTTP/1.1 200")
        assert await reader.readexactly(2) == b"OK"
    # Uma mutação no meio da conexão derruba a conexão com 403.
    writer.write(b"POST /containers/x/start HTTP/1.1\r\nHost: d\r\nContent-Length: 0\r\n\r\n")
    await writer.drain()
    resp = await reader.read()
    assert resp.startswith(b"HTTP/1.1 403")
    writer.close()
