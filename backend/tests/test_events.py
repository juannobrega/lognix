import asyncio
import copy

from httpx import AsyncClient

from tests import fake_docker
from tests.conftest import FakeAlloy
from tests.fake_docker import FakeDocker, make_event
from tests.fake_ssh import FakeSshBackend
from tests.test_containers import _connected_host


async def _wait(cond, timeout: float = 5.0, msg: str = "") -> None:  # type: ignore[no-untyped-def]
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if await cond():
            return
        await asyncio.sleep(0.05)
    raise AssertionError(msg or "condição não satisfeita a tempo")


async def _mark(authed: AsyncClient, host_id: str, name: str) -> dict:  # type: ignore[type-arg]
    inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
    c = next(x for x in inv if x["name"] == name)
    r = await authed.put(
        f"/api/v1/hosts/{host_id}/containers/monitored", json={"container_ids": [c["id"]]}
    )
    assert r.status_code == 200
    return c


async def test_host_connect_records_event_and_starts_workers(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str]
) -> None:
    fake, _, _ = fake_env
    host_id = await _connected_host(authed)
    events = (await authed.get(f"/api/v1/hosts/{host_id}/events")).json()
    assert any(e["type"] == "connected" for e in events)
    # Listener de eventos abriu o stream pelo proxy.
    await _wait(
        lambda: asyncio.sleep(0, fake.events_connections >= 1), msg="stream /events não abriu"
    )
    assert any(t.startswith("/events") for _, t in fake.requests)


async def test_new_container_notification_and_monitor_action(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str], fake_alloy: FakeAlloy
) -> None:
    fake, _, _ = fake_env
    host_id = await _connected_host(authed)
    assert (await authed.get("/api/v1/notifications")).json() == []

    original = copy.deepcopy(fake_docker.CONTAINERS)
    worker_c = {
        "Id": "ee11" + "0" * 60,
        "Names": ["/worker"],
        "Image": "ghcr.io/x/worker:2.0",
        "ImageID": "sha256:cccc",
        "State": "running",
        "Status": "Up",
        "Labels": {},
    }
    try:
        fake_docker.CONTAINERS.append(worker_c)
        fake.emit(make_event("start", worker_c))

        async def has_notification() -> bool:
            ns = (await authed.get("/api/v1/notifications")).json()
            return any(
                n["type"] == "new_container" and n["payload"]["name"] == "worker" for n in ns
            )

        await _wait(has_notification, msg="notificação new_container não chegou")
        ns = (await authed.get("/api/v1/notifications")).json()
        n = next(n for n in ns if n["type"] == "new_container")
        assert n["host_id"] == host_id and n["container_id"]
        assert (await authed.get("/api/v1/notifications/count")).json() == {"new": 1}

        # Ação inline "monitorar": marca o container e a notificação pode ser vista.
        r = await authed.put(
            f"/api/v1/hosts/{host_id}/containers/monitored",
            json={"container_ids": [n["container_id"]]},
        )
        assert r.json()["alloy"]["containers_in_config"] == 1
        assert (await authed.post(f"/api/v1/notifications/{n['id']}/seen")).status_code == 204
        assert (await authed.get("/api/v1/notifications")).json() == []
        assert len((await authed.get("/api/v1/notifications/history")).json()) == 1

        # Mesmo evento repetido não duplica a notificação (dedupe de `new`).
        fake.emit(make_event("start", worker_c))
        await asyncio.sleep(0.3)
        assert (await authed.get("/api/v1/notifications/count")).json() == {"new": 0}
    finally:
        fake_docker.CONTAINERS[:] = original


async def test_docker_events_recorded_only_for_monitored(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str], fake_alloy: FakeAlloy
) -> None:
    fake, _, _ = fake_env
    host_id = await _connected_host(authed)
    api_raw, db_raw = fake_docker.CONTAINERS[0], fake_docker.CONTAINERS[1]
    api = await _mark(authed, host_id, "api")
    inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
    db = next(c for c in inv if c["name"] == "db")

    await _wait(lambda: asyncio.sleep(0, fake.events_connections >= 1))
    fake.emit(make_event("die", api_raw, exitCode="137"))
    fake.emit(make_event("oom", api_raw))
    fake.emit(make_event("health_status: unhealthy", api_raw))
    fake.emit(make_event("die", db_raw, exitCode="1"))  # não monitorado: ignorado

    async def recorded() -> bool:
        evs = (await authed.get(f"/api/v1/projects/{api['id']}/events")).json()
        return len(evs) >= 3

    await _wait(recorded, msg="eventos não gravados")
    evs = (await authed.get(f"/api/v1/projects/{api['id']}/events")).json()
    types = {e["type"] for e in evs}
    assert {"die", "oom", "health_status"} <= types
    die = next(e for e in evs if e["type"] == "die")
    assert die["exit_code"] == 137
    assert (await authed.get(f"/api/v1/projects/{db['id']}/events")).json() == []


async def test_redeploy_keeps_project_identity(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str], fake_alloy: FakeAlloy
) -> None:
    fake, _, _ = fake_env
    host_id = await _connected_host(authed)
    api = await _mark(authed, host_id, "api")
    original = copy.deepcopy(fake_docker.CONTAINERS)
    reloads = fake_alloy.reloads
    try:
        # docker compose up recria `api` com outro ID e imagem nova, mesmo projeto/serviço.
        new_api = copy.deepcopy(original[0])
        new_api["Id"] = "ab12" + "0" * 60
        new_api["Image"] = "ghcr.io/x/api:1.6.0"
        new_api["ImageID"] = "sha256:dddd"
        fake_docker.CONTAINERS[:] = [new_api, original[1]]
        fake.emit(make_event("destroy", original[0]))
        fake.emit(make_event("start", new_api))

        async def redeployed() -> bool:
            p = (await authed.get(f"/api/v1/projects/{api['id']}")).json()
            return p.get("docker_id") == new_api["Id"]

        await _wait(redeployed, msg="redeploy não reconhecido")
        p = (await authed.get(f"/api/v1/projects/{api['id']}")).json()
        assert p["monitored"] is True and p["image"] == "ghcr.io/x/api:1.6.0"
        evs = (await authed.get(f"/api/v1/projects/{api['id']}/events")).json()
        rd = next(e for e in evs if e["type"] == "redeploy")
        assert (
            rd["previous_image"] == "ghcr.io/x/api:1.5.0"
            and rd["new_image"] == "ghcr.io/x/api:1.6.0"
        )
        # Sem notificação de container novo, sem excluídos, Alloy reaplicado com o novo ID.
        assert all(
            n["type"] != "new_container" for n in (await authed.get("/api/v1/notifications")).json()
        )
        assert (await authed.get("/api/v1/projects/excluded")).json() == []
        assert fake_alloy.reloads > reloads
        import os

        assert new_api["Id"] in open(os.environ["ALLOY_CONFIG_PATH"], encoding="utf-8").read()
        assert (await authed.get("/api/v1/projects")).json()[0]["id"] == api["id"]
    finally:
        fake_docker.CONTAINERS[:] = original


async def test_removed_container_goes_to_excluded(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str], fake_alloy: FakeAlloy
) -> None:
    fake, _, _ = fake_env
    host_id = await _connected_host(authed)
    api = await _mark(authed, host_id, "api")
    original = copy.deepcopy(fake_docker.CONTAINERS)
    try:
        fake_docker.CONTAINERS[:] = [original[1]]
        fake.emit(make_event("destroy", original[0]))

        async def excluded() -> bool:
            ex = (await authed.get("/api/v1/projects/excluded")).json()
            return any(c["id"] == api["id"] for c in ex)

        await _wait(excluded, msg="container não foi para excluídos")
        ex = (await authed.get(f"/api/v1/hosts/{host_id}/containers/excluded")).json()
        assert (
            ex[0]["id"] == api["id"] and ex[0]["monitored"] is False and ex[0]["state"] == "removed"
        )
        assert (await authed.get("/api/v1/projects")).json() == []
        # Insights/eventos do projeto continuam acessíveis.
        assert (await authed.get(f"/api/v1/projects/{api['id']}")).status_code == 200
        host_events = (await authed.get(f"/api/v1/hosts/{host_id}/events")).json()
        assert any(e["type"] == "container_removed" for e in host_events)
    finally:
        fake_docker.CONTAINERS[:] = original


async def test_inspect_stores_env_names_only(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str], fake_alloy: FakeAlloy
) -> None:
    host_id = await _connected_host(authed)
    api = await _mark(authed, host_id, "api")

    async def inspected() -> bool:
        p = (await authed.get(f"/api/v1/projects/{api['id']}")).json()
        return bool(p["env"].get("names"))

    await _wait(inspected, msg="inspeção não aconteceu")
    p = (await authed.get(f"/api/v1/projects/{api['id']}")).json()
    assert p["env"]["names"] == ["APP_VERSION", "DATABASE_URL", "NODE_ENV"]
    assert p["env"]["safe"] == {"APP_VERSION": "1.5.0", "NODE_ENV": "production"}
    assert "secret" not in str(p["env"])


async def test_host_disconnect_and_reconnect_notifications(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str]
) -> None:
    _, backend, _ = fake_env
    host_id = await _connected_host(authed)
    # Simula queda: a próxima conexão SSH falha, e o ping atual falha ao fechar o docker falso?
    # Mais simples: força o runner a registrar uma falha pela mudança de fingerprint.
    backend.fingerprint = "SHA256:OUTRA000000000000000000000000000000000000000"
    rec = await authed.post(f"/api/v1/hosts/{host_id}/reconnect")
    from tests.test_hosts import _wait_validation

    result = await _wait_validation(authed, rec.json()["validation_id"])
    assert result["status"] == "failed"

    async def notified() -> bool:
        ns = (await authed.get("/api/v1/notifications")).json()
        return any(n["type"] == "fingerprint_changed" for n in ns)

    await _wait(notified, msg="notificação de fingerprint não chegou")
    acc = await authed.post(f"/api/v1/hosts/{host_id}/accept-fingerprint")
    assert (await _wait_validation(authed, acc.json()["validation_id"]))["status"] == "ok"

    async def reconnected() -> bool:
        ns = (await authed.get("/api/v1/notifications")).json()
        return any(n["type"] == "host_reconnected" for n in ns)

    await _wait(reconnected, msg="notificação de reconexão não chegou")
    marked = (await authed.post("/api/v1/notifications/seen-all")).json()["marked"]
    assert marked >= 2


async def test_redeploy_prefers_monitored_recent_row(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str], fake_alloy: FakeAlloy
) -> None:
    """Duas linhas removidas com a mesma identidade: a monitorada e mais recente ganha."""
    fake, _, _ = fake_env
    host_id = await _connected_host(authed)
    original = copy.deepcopy(fake_docker.CONTAINERS)
    try:
        # 1º redeploy sem monitorar: deixa uma linha `removed` antiga com identidade demo/api.
        v2 = copy.deepcopy(original[0])
        v2["Id"] = "b1" + "0" * 62
        v2["Image"] = "ghcr.io/x/api:2"
        fake_docker.CONTAINERS[:] = [v2, original[1]]
        fake.emit(make_event("destroy", original[0]))
        fake.emit(make_event("start", v2))

        async def has_v2() -> bool:
            inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
            return any(c["docker_id"] == v2["Id"] for c in inv)

        await _wait(has_v2)
        inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
        current = next(c for c in inv if c["docker_id"] == v2["Id"])
        # Marca a linha atual como monitorada e faz novo redeploy.
        await authed.put(
            f"/api/v1/hosts/{host_id}/containers/monitored", json={"container_ids": [current["id"]]}
        )
        v3 = copy.deepcopy(v2)
        v3["Id"] = "c1" + "0" * 62
        v3["Image"] = "ghcr.io/x/api:3"
        fake_docker.CONTAINERS[:] = [v3, original[1]]
        fake.emit(make_event("destroy", v2))
        fake.emit(make_event("start", v3))

        async def redeployed() -> bool:
            p = (await authed.get(f"/api/v1/projects/{current['id']}")).json()
            return p.get("docker_id") == v3["Id"] and p.get("monitored") is True

        await _wait(redeployed, msg="redeploy não manteve a linha monitorada")
        assert (await authed.get("/api/v1/projects")).json()[0]["id"] == current["id"]
    finally:
        fake_docker.CONTAINERS[:] = original


async def test_redeploy_via_compose_rename(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str], fake_alloy: FakeAlloy
) -> None:
    """`docker compose up` renomeia o antigo para <id>_nome, cria o novo e só depois destrói
    o antigo. Durante a coexistência o projeto precisa migrar para o novo container."""
    fake, _, _ = fake_env
    host_id = await _connected_host(authed)
    api = await _mark(authed, host_id, "api")
    original = copy.deepcopy(fake_docker.CONTAINERS)
    try:
        old = copy.deepcopy(original[0])
        old["Names"] = ["/9c1d00000000_api"]
        new = copy.deepcopy(original[0])
        new["Id"] = "dd44" + "0" * 60
        new["Image"] = "ghcr.io/x/api:1.7.0"
        # Fase 1: coexistência.
        fake_docker.CONTAINERS[:] = [old, new, original[1]]
        fake.emit(make_event("rename", old))
        fake.emit(make_event("start", new))

        async def migrated() -> bool:
            p = (await authed.get(f"/api/v1/projects/{api['id']}")).json()
            return p.get("docker_id") == new["Id"]

        await _wait(migrated, msg="projeto não migrou para o container novo")
        inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
        assert not any(c["name"].startswith("9c1d00000000_") for c in inv), "zumbi virou linha"
        # Fase 2: antigo destruído.
        fake_docker.CONTAINERS[:] = [new, original[1]]
        fake.emit(make_event("destroy", old))
        await asyncio.sleep(0.5)
        p = (await authed.get(f"/api/v1/projects/{api['id']}")).json()
        assert p["monitored"] is True and p["state"] == "running" and p["docker_id"] == new["Id"]
        assert (await authed.get("/api/v1/projects/excluded")).json() == []
        assert all(
            n["type"] != "new_container" for n in (await authed.get("/api/v1/notifications")).json()
        )
        evs = (await authed.get(f"/api/v1/projects/{api['id']}/events")).json()
        assert any(e["type"] == "redeploy" and e["new_image"] == "ghcr.io/x/api:1.7.0" for e in evs)
    finally:
        fake_docker.CONTAINERS[:] = original
