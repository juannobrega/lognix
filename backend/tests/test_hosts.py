import asyncio
import os
import tempfile
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from lognix.hosts import supervisor as sup_module
from lognix.hosts.supervisor import TunnelSupervisor
from tests.fake_docker import FakeDocker
from tests.fake_ssh import FakeSshBackend

KEY = "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----\n"


@pytest.fixture
async def fake_env() -> AsyncIterator[tuple[FakeDocker, FakeSshBackend, str]]:
    tmp = tempfile.mkdtemp(prefix="lgx", dir="/tmp")
    docker_path = os.path.join(tmp, "docker.sock")
    fake = FakeDocker(docker_path)
    await fake.start()
    backend = FakeSshBackend(docker_path)
    supervisor = TunnelSupervisor(backend=backend, tunnels_dir=os.path.join(tmp, "tunnels"))
    sup_module.set_supervisor(supervisor)
    try:
        yield fake, backend, tmp
    finally:
        await supervisor.stop()
        sup_module.set_supervisor(None)
        await fake.stop()


async def _wait_validation(client: AsyncClient, vid: str, timeout: float = 10) -> dict:  # type: ignore[type-arg]
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        data = (await client.get(f"/api/v1/hosts/validations/{vid}")).json()
        if data["status"] != "running":
            return data
        await asyncio.sleep(0.05)
    raise AssertionError("validação não terminou")


HOST = {
    "name": "vm-01",
    "address": "127.0.0.1",
    "ssh_port": 22,
    "ssh_user": "deploy",
    "ssh_auth_method": "password",
    "password": "deploy123",
}


async def test_create_host_full_validation(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str]
) -> None:
    fake, backend, _ = fake_env
    # Porta 22 local pode não responder; aponte para a porta do FakeDocker? É socket Unix.
    # A etapa 1 faz TCP real: usamos um listener TCP efêmero local.
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        resp = await authed.post("/api/v1/hosts", json={**HOST, "ssh_port": port})
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["host"]["status"] == "pending"
        assert body["host"]["ssh_auth_method"] == "password"

        result = await _wait_validation(authed, body["validation_id"])
        assert result["status"] == "ok", result
        assert [s["status"] for s in result["steps"]] == ["ok"] * 6
        assert "Docker 27.1.1" in result["steps"][4]["detail"]
        assert len(result["containers"]) == 2
        assert result["containers"][0]["compose_project"] == "demo"

        host = (await authed.get(f"/api/v1/hosts/{body['host']['id']}")).json()
        assert host["status"] == "connected"
        assert host["docker_version"] == "27.1.1"
        assert host["ssh_host_key_fingerprint"] == backend.fingerprint
        assert host["tunnel"]["socket_path"].endswith(f"{host['id']}.sock")
        assert os.path.exists(host["tunnel"]["socket_path"])

        containers = (await authed.get(f"/api/v1/hosts/{host['id']}/containers")).json()
        assert {c["name"] for c in containers} == {"api", "db"}
        # Tudo que chegou ao Docker passou pelo proxy e foi GET.
        assert all(m == "GET" for m, _ in fake.requests)

        # Remoção: oculta e encerra o túnel.
        assert (await authed.delete(f"/api/v1/hosts/{host['id']}")).status_code == 204
        assert (await authed.get(f"/api/v1/hosts/{host['id']}")).status_code == 404
        assert (await authed.get("/api/v1/hosts")).json() == []
        await asyncio.sleep(0.1)
        assert not os.path.exists(host["tunnel"]["socket_path"])
    finally:
        server.close()


async def test_validation_fails_on_bad_password_with_action(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str]
) -> None:
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        resp = await authed.post(
            "/api/v1/hosts", json={**HOST, "ssh_port": port, "password": "errada"}
        )
        result = await _wait_validation(authed, resp.json()["validation_id"])
        assert result["status"] == "failed"
        assert result["steps"][0]["status"] == "ok"
        assert result["steps"][1]["status"] == "failed"
        assert result["steps"][1]["action"]
        assert result["steps"][2]["status"] == "pending"
    finally:
        server.close()


async def test_validation_fails_on_unreachable_port(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str]
) -> None:
    resp = await authed.post("/api/v1/hosts", json={**HOST, "ssh_port": 1})
    result = await _wait_validation(authed, resp.json()["validation_id"])
    assert result["status"] == "failed"
    assert result["steps"][0]["status"] == "failed"
    assert "firewall" in result["steps"][0]["action"]


async def test_fingerprint_mismatch_blocks_and_accept_recovers(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str]
) -> None:
    _, backend, _ = fake_env
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        resp = await authed.post("/api/v1/hosts", json={**HOST, "ssh_port": port})
        host_id = resp.json()["host"]["id"]
        assert (await _wait_validation(authed, resp.json()["validation_id"]))["status"] == "ok"

        # O servidor "troca" de chave.
        backend.fingerprint = "SHA256:OUTRA000000000000000000000000000000000000000"
        rec = await authed.post(f"/api/v1/hosts/{host_id}/reconnect")
        result = await _wait_validation(authed, rec.json()["validation_id"])
        assert result["status"] == "failed"
        assert result["steps"][2]["status"] == "failed"
        assert "chave do servidor mudou" in result["steps"][2]["message"]

        acc = await authed.post(f"/api/v1/hosts/{host_id}/accept-fingerprint")
        result = await _wait_validation(authed, acc.json()["validation_id"])
        assert result["status"] == "ok"
        host = (await authed.get(f"/api/v1/hosts/{host_id}")).json()
        assert host["ssh_host_key_fingerprint"] == backend.fingerprint
    finally:
        server.close()


async def test_schema_requires_credential_for_method(authed: AsyncClient) -> None:
    resp = await authed.post("/api/v1/hosts", json={**HOST, "password": None})
    assert resp.status_code == 422
    resp = await authed.post("/api/v1/hosts", json={**HOST, "ssh_auth_method": "key"})
    assert resp.status_code == 422
    resp = await authed.post("/api/v1/hosts", json={**HOST, "name": "nome inválido"})
    assert resp.status_code == 422


async def test_duplicate_name(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str]
) -> None:
    assert (await authed.post("/api/v1/hosts", json={**HOST, "ssh_port": 1})).status_code == 202
    dup = await authed.post("/api/v1/hosts", json={**HOST, "ssh_port": 1})
    assert dup.status_code == 409
