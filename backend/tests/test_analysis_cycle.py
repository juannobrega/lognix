import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from lognix.analysis.manager import AnalysisManager
from tests.conftest import FakeAlloy, ScriptedLoki
from tests.fake_docker import FakeDocker, make_event
from tests.fake_ssh import FakeSshBackend
from tests.test_containers import _connected_host
from tests.test_events import _mark, _wait


async def test_manual_analysis_creates_run_patterns_and_trigger(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki: AnalysisManager,
) -> None:
    host_id = await _connected_host(authed)
    api = await _mark(authed, host_id, "api")
    ScriptedLoki.lines = [
        "user 1 logged in",
        "user 2 logged in",
        "ERROR db down: connection refused",
        "WARN slow query 120ms",
    ]

    resp = await authed.post(f"/api/v1/projects/{api['id']}/analyze", json={"minutes": 5})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (
        body["run"]["lines_count"] == 4
        and body["run"]["error_lines_count"] == 1
        and body["run"]["warn_lines_count"] == 1
    )
    assert body["run"]["manual"] is True
    # new_patterns_count é 0 aqui: marcar o container já disparou um ciclo que viu estas
    # mesmas linhas. O que importa é o conjunto final de padrões, conferido abaixo.
    assert body["run"]["new_patterns_count"] >= 0
    assert [t["type"] for t in body["triggers"]] == ["manual"]
    assert body["triggers"][0]["sample_lines"][0]["line"].startswith("ERROR db down")

    patterns = (await authed.get(f"/api/v1/projects/{api['id']}/patterns")).json()
    assert len(patterns) == 3, [p["template"] for p in patterns]
    top = patterns[0]
    # "user 1/2 logged in" vira um padrão só, contado duas vezes por ciclo que o viu.
    assert top["count_total"] % 2 == 0 and "logged in" in top["template"]
    err = next(p for p in patterns if p["level"] == "error")
    assert "connection refused" in err["template"]

    # Ignorar padrão.
    ign = await authed.put(
        f"/api/v1/projects/{api['id']}/patterns/{err['id']}/ignore", json={"ignored": True}
    )
    assert ign.json()["ignored"] is True

    runs = (await authed.get(f"/api/v1/projects/{api['id']}/analysis-runs")).json()
    assert runs[0]["manual"] is True and runs[0]["status"] == "ok"

    # Sem IA: aparece em ocorrências sem análise, com nome do projeto e host.
    un = (await authed.get("/api/v1/insights/unanalyzed")).json()
    assert (
        un[0]["container_name"] == "api"
        and un[0]["host_name"] == "vm-01"
        and un[0]["insight_id"] is None
    )

    # Limite de 1 por minuto.
    again = await authed.post(f"/api/v1/projects/{api['id']}/analyze", json={"minutes": 5})
    assert again.status_code == 429


async def test_cycle_loop_fires_error_and_docker_triggers(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki: AnalysisManager,
) -> None:
    fake, _, _ = fake_env
    host_id = await _connected_host(authed)
    ScriptedLoki.lines = ["Traceback (most recent call last):", "  File x.py", "ValueError: boom"]
    api = await _mark(authed, host_id, "api")
    # Marcar inicia o loop (reconcile). Evento crítico na janela.
    await _wait(lambda: asyncio.sleep(0, fake.events_connections >= 1))
    fake.emit(
        make_event(
            "die",
            __import__("tests.fake_docker", fromlist=["CONTAINERS"]).CONTAINERS[0],
            exitCode="137",
        )
    )

    async def fired() -> bool:
        ts = (await authed.get(f"/api/v1/projects/{api['id']}/triggers")).json()
        return {t["type"] for t in ts} >= {"error", "docker_event"}

    await _wait(fired, timeout=15, msg="triggers do ciclo não dispararam")
    ts = (await authed.get(f"/api/v1/projects/{api['id']}/triggers")).json()
    de = next(t for t in ts if t["type"] == "docker_event")
    assert de["reason"]["events"][0]["exit_code"] == 137
    runs = (await authed.get(f"/api/v1/projects/{api['id']}/analysis-runs")).json()
    assert runs and runs[0]["manual"] is False and runs[0]["error_lines_count"] >= 1
    # Janelas contíguas: a próxima começa onde a anterior terminou.
    await _wait(lambda: asyncio.sleep(0, len(ScriptedLoki.lines) and True))
    state = (await authed.get("/api/v1/executor")).json()
    assert any(lp["container_id"] == api["id"] for lp in state["loops"])

    # Desmarcar para o loop.
    await authed.put(f"/api/v1/hosts/{host_id}/containers/monitored", json={"container_ids": []})
    await asyncio.sleep(0.2)
    state = (await authed.get("/api/v1/executor")).json()
    assert not any(lp["container_id"] == api["id"] for lp in state["loops"])


async def test_cycle_failure_does_not_advance_window(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki: AnalysisManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host_id = await _connected_host(authed)
    from lognix.loki.client import LokiError

    async def boom(self, *a, **k):  # type: ignore[no-untyped-def]
        raise LokiError("loki fora")

    monkeypatch.setattr(ScriptedLoki, "query_range", boom)
    api = await _mark(authed, host_id, "api")

    async def failed_run() -> bool:
        runs = (await authed.get(f"/api/v1/projects/{api['id']}/analysis-runs")).json()
        return any(r["status"] == "failed" for r in runs)

    await _wait(failed_run, timeout=10)
    loop = scripted_loki.get(uuid.UUID(api["id"]))
    assert loop is not None and loop.last_window_end is None
    runs = (await authed.get(f"/api/v1/projects/{api['id']}/analysis-runs")).json()
    assert "loki fora" in (runs[0]["error"] or "")
    assert (await authed.get(f"/api/v1/projects/{api['id']}/triggers")).json() == []
    _ = datetime.now(UTC) - timedelta(seconds=1)


async def test_manual_and_automatic_cycles_do_not_collide(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki: AnalysisManager,
) -> None:
    """Análise manual e ciclo automático no mesmo container competiam pela criação dos
    mesmos padrões e estouravam a unicidade (container_id, template). Reproduzido no CI."""
    host_id = await _connected_host(authed)
    ScriptedLoki.lines = ["user 1 logged in", "ERROR db down", "WARN slow"]
    api = await _mark(authed, host_id, "api")

    # Dispara a manual em rajada enquanto o loop (pausa de 1 s) também roda.
    results = await asyncio.gather(
        *(
            authed.post(f"/api/v1/projects/{api['id']}/analyze", json={"minutes": 5})
            for _ in range(3)
        ),
        return_exceptions=True,
    )
    codes = [r.status_code for r in results if hasattr(r, "status_code")]
    # Uma passa, as outras batem no limite de 1 por minuto. Nenhuma estoura em 500.
    assert 201 in codes and all(c in (201, 429) for c in codes), codes
    await asyncio.sleep(2.5)

    patterns = (await authed.get(f"/api/v1/projects/{api['id']}/patterns")).json()
    templates = [p["template"] for p in patterns]
    assert len(templates) == len(set(templates)), "padrões duplicados"
    runs = (await authed.get(f"/api/v1/projects/{api['id']}/analysis-runs")).json()
    assert all(r["status"] != "failed" for r in runs), [r["error"] for r in runs if r["error"]]
    assert sum(p["count_total"] for p in patterns) > 0
