import asyncio
import os

from httpx import AsyncClient

from tests.conftest import FakeAlloy
from tests.fake_docker import FakeDocker
from tests.fake_ssh import FakeSshBackend
from tests.test_hosts import HOST, _wait_validation


async def _connected_host(authed: AsyncClient) -> str:
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    resp = await authed.post("/api/v1/hosts", json={**HOST, "ssh_port": port})
    result = await _wait_validation(authed, resp.json()["validation_id"])
    assert result["status"] == "ok", result
    server.close()
    return str(resp.json()["host"]["id"])


async def test_inventory_and_monitoring_flow(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
) -> None:
    host_id = await _connected_host(authed)

    # Validação persistiu o inventário com ids do Lognix e nada monitorado.
    inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
    assert {c["name"] for c in inv} == {"api", "db"}
    assert all(c["monitored"] is False for c in inv)
    api = next(c for c in inv if c["name"] == "api")
    assert api["compose_project"] == "demo" and api["state"] == "running"

    # Ninguém monitorado ainda: projetos vazio.
    assert (await authed.get("/api/v1/projects")).json() == []
    reloads_before = fake_alloy.reloads

    # Marca `api`.
    resp = await authed.put(
        f"/api/v1/hosts/{host_id}/containers/monitored", json={"container_ids": [api["id"]]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["alloy"]["reload_ok"] is True
    assert body["alloy"]["hosts_in_config"] == 1 and body["alloy"]["containers_in_config"] == 1
    assert fake_alloy.reloads == reloads_before + 1
    marked = next(c for c in body["containers"] if c["name"] == "api")
    assert marked["monitored"] is True and marked["monitored_since"]

    # Arquivo gerado contém o filtro pelo ID Docker e o container_id do Lognix.
    content = open(os.environ["ALLOY_CONFIG_PATH"], encoding="utf-8").read()
    assert api["docker_id"] in content and api["id"] in content
    assert f"/{host_id}.sock" in content
    assert "77ab" not in content  # db não monitorado

    # Projetos lista o monitorado com o host.
    projects = (await authed.get("/api/v1/projects")).json()
    assert [p["name"] for p in projects] == ["api"]
    assert projects[0]["host_name"] == "vm-01" and projects[0]["kind"] == "image"
    detail = (await authed.get(f"/api/v1/projects/{api['id']}")).json()
    assert detail["id"] == api["id"]

    # Config versionada.
    cfg = (await authed.get(f"/api/v1/hosts/{host_id}/alloy-config")).json()
    assert cfg["current"] == content
    assert cfg["versions"][0]["reload_ok"] is True
    assert "monitorados = api" in cfg["versions"][0]["reason"]

    # Desmarca tudo: bloco do host sai.
    resp = await authed.put(
        f"/api/v1/hosts/{host_id}/containers/monitored", json={"container_ids": []}
    )
    assert resp.json()["alloy"]["hosts_in_config"] == 0
    assert "discovery.docker" not in open(os.environ["ALLOY_CONFIG_PATH"], encoding="utf-8").read()


async def test_reload_failure_restores_previous_config(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
) -> None:
    host_id = await _connected_host(authed)
    inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
    api = next(c for c in inv if c["name"] == "api")
    ok = await authed.put(
        f"/api/v1/hosts/{host_id}/containers/monitored", json={"container_ids": [api["id"]]}
    )
    good = open(os.environ["ALLOY_CONFIG_PATH"], encoding="utf-8").read()
    assert ok.json()["alloy"]["reload_ok"]

    fake_alloy.fail = True
    db = next(c for c in inv if c["name"] == "db")
    resp = await authed.put(
        f"/api/v1/hosts/{host_id}/containers/monitored",
        json={"container_ids": [api["id"], db["id"]]},
    )
    assert resp.status_code == 200
    assert resp.json()["alloy"]["reload_ok"] is False
    assert "HTTP 400" in resp.json()["alloy"]["error"]
    # Arquivo voltou ao conteúdo anterior válido.
    assert open(os.environ["ALLOY_CONFIG_PATH"], encoding="utf-8").read() == good
    versions = (await authed.get(f"/api/v1/hosts/{host_id}/alloy-config")).json()["versions"]
    assert versions[0]["reload_ok"] is False and versions[1]["reload_ok"] is True


async def test_removing_host_regenerates_config(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
) -> None:
    host_id = await _connected_host(authed)
    inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
    await authed.put(
        f"/api/v1/hosts/{host_id}/containers/monitored", json={"container_ids": [inv[0]["id"]]}
    )
    assert "discovery.docker" in open(os.environ["ALLOY_CONFIG_PATH"], encoding="utf-8").read()
    assert (await authed.delete(f"/api/v1/hosts/{host_id}")).status_code == 204
    assert "discovery.docker" not in open(os.environ["ALLOY_CONFIG_PATH"], encoding="utf-8").read()
    assert (await authed.get("/api/v1/projects")).json() == []


async def test_monitored_container_disappearing_regenerates_config(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
) -> None:
    _ = fake_env
    host_id = await _connected_host(authed)
    inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
    api = next(c for c in inv if c["name"] == "api")
    await authed.put(
        f"/api/v1/hosts/{host_id}/containers/monitored", json={"container_ids": [api["id"]]}
    )
    assert api["docker_id"] in open(os.environ["ALLOY_CONFIG_PATH"], encoding="utf-8").read()

    # O container `api` some do Docker (ex.: recriado com outro ID).
    from tests import fake_docker

    original = list(fake_docker.CONTAINERS)
    fake_docker.CONTAINERS[:] = [c for c in original if c["Names"] != ["/api"]]
    try:
        reloads = fake_alloy.reloads
        inv2 = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
        assert {c["name"] for c in inv2} == {"db"}
        assert fake_alloy.reloads == reloads + 1
        content = open(os.environ["ALLOY_CONFIG_PATH"], encoding="utf-8").read()
        assert api["docker_id"] not in content and "discovery.docker" not in content
        assert (await authed.get("/api/v1/projects")).json() == []
    finally:
        fake_docker.CONTAINERS[:] = original
