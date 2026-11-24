import asyncio

from httpx import AsyncClient

from tests.conftest import FakeAlloy
from tests.fake_docker import FakeDocker
from tests.fake_ssh import FakeSshBackend
from tests.test_containers import _connected_host
from tests.test_events import _mark


async def test_metrics_endpoint_exposes_series(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str], fake_alloy: FakeAlloy
) -> None:
    host_id = await _connected_host(authed)
    await _mark(authed, host_id, "api")
    resp = await authed.get("/api/v1/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    for metric in (
        "lognix_tunnels",
        "lognix_docker_proxy_requests_total",
        "lognix_analysis_loops",
        "http_request_duration_seconds",
        "lognix_cycles_total",
    ):
        assert metric in body, metric
    # O proxy já atendeu GETs durante a validação.
    assert 'lognix_docker_proxy_requests_total{outcome="allowed"}' in body
    assert 'lognix_tunnels{state="connected"} 1.0' in body


async def test_metrics_count_rejected_requests(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str]
) -> None:
    import httpx

    host_id = await _connected_host(authed)
    host = (await authed.get(f"/api/v1/hosts/{host_id}")).json()
    socket_path = host["tunnel"]["socket_path"]
    async with httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(uds=socket_path), base_url="http://d"
    ) as c:
        assert (await c.post("/containers/x/restart")).status_code == 403
    body = (await authed.get("/api/v1/metrics")).text
    line = next(
        ln
        for ln in body.splitlines()
        if ln.startswith('lognix_docker_proxy_requests_total{outcome="rejected"}')
    )
    assert float(line.split()[-1]) >= 1.0
    # E a tela Sistema reporta o mesmo.
    sysinfo = (await authed.get("/api/v1/system")).json()
    assert sysinfo["proxy_rejected_total"] >= 1


async def test_system_endpoint(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str], fake_alloy: FakeAlloy
) -> None:
    unauth = await AsyncClient(transport=authed._transport, base_url="http://test").get(
        "/api/v1/system"
    )
    assert unauth.status_code == 401

    host_id = await _connected_host(authed)
    await _mark(authed, host_id, "api")
    await asyncio.sleep(0.1)
    s = (await authed.get("/api/v1/system")).json()
    assert s["version"]
    assert s["components"]["postgres"]["ok"] is True
    assert s["retention_days"] == 15 and s["analysis_interval_seconds"] == 30
    assert s["counts"]["hosts"] == 1 and s["counts"]["hosts_connected"] == 1
    assert s["counts"]["containers"] == 2 and s["counts"]["monitored"] == 1
    kinds = {lp["kind"]: lp for lp in s["loops"]}
    assert kinds["tunnels"]["count"] == 1
    assert kinds["tunnels"]["detail"][0]["host"] == "vm-01"
    assert kinds["tunnels"]["detail"][0]["connected"] is True
    assert kinds["analysis"]["count"] >= 0
    assert any(v["path"] for v in s["volumes"])
    assert s["uptime_seconds"] >= 0
