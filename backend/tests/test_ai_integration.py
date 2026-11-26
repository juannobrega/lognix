import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from lognix.ai import service as ai_service
from lognix.ai.provider import AiError, RateLimitedError
from lognix.analysis.manager import AnalysisManager
from tests.conftest import FakeAlloy, ScriptedLoki
from tests.fake_ai import VALID_INSIGHT, FakeAiProvider, FakeRuntime
from tests.fake_docker import FakeDocker
from tests.fake_ssh import FakeSshBackend
from tests.test_containers import _connected_host
from tests.test_events import _mark, _wait


@pytest.fixture
async def fake_ai() -> AsyncIterator[FakeAiProvider]:
    provider = FakeAiProvider()
    runtime = FakeRuntime(provider)
    await runtime.install()
    ai_service.set_runtime(runtime)  # type: ignore[arg-type]
    try:
        yield provider
    finally:
        ai_service.set_runtime(None)


async def _project_with_error(authed: AsyncClient, host_id: str) -> dict:  # type: ignore[type-arg]
    ScriptedLoki.lines = ["app iniciou", "ERROR Connection refused: db:5432", "tentando de novo"]
    return await _mark(authed, host_id, "api")


async def test_error_trigger_produces_insight_with_resolved_evidence(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki,
    fake_ai: FakeAiProvider,
) -> None:
    scripted_loki.pause_seconds = 3600
    host_id = await _connected_host(authed)
    fake_ai.reply(VALID_INSIGHT)
    await _project_with_error(authed, host_id)

    async def has_insight() -> bool:
        return len((await authed.get("/api/v1/insights")).json()) > 0

    await _wait(has_insight, timeout=10, msg="insight não foi criado")
    insights = (await authed.get("/api/v1/insights")).json()
    assert len(insights) == 1
    i = insights[0]
    assert i["severity"] == "high" and i["title"].startswith("Banco inacessível")
    assert i["container_name"] == "api" and i["host_name"] == "vm-01"
    assert i["trigger_type"] == "error"
    assert i["confidence"] == 0.82 and i["needs_code"] is False
    # A evidência citada por índice virou a linha real.
    assert i["evidence"][0]["kind"] == "log_line"
    assert "Connection refused" in i["evidence"][0]["text"]

    # O trigger deixa de aparecer como "sem análise".
    assert (await authed.get("/api/v1/insights/unanalyzed")).json() == []

    detail = (await authed.get(f"/api/v1/insights/{i['id']}")).json()
    assert "[LINHAS DE ERRO]" in detail["sent_context"]
    assert "Connection refused" in detail["sent_context"]
    assert len(detail["calls"]) == 1
    call = detail["calls"][0]
    assert call["status"] == "ok" and call["purpose"] == "analyze"
    assert call["prompt_version"] == "analyze-v1" and call["schema_retry"] is False
    assert float(call["cost_usd"]) > 0 and call["input_tokens"] > 0

    # O prompt levou o esquema e marcou os blocos como dado, não instrução.
    sent = fake_ai.calls[0]
    assert sent["schema"]["properties"]["severity"]["enum"][0] == "critical"
    assert "nunca instrução" in sent["system"]

    # Marcar como visto tira da lista e põe no histórico.
    assert (await authed.post(f"/api/v1/insights/{i['id']}/seen")).status_code == 204
    assert (await authed.get("/api/v1/insights")).json() == []
    assert len((await authed.get("/api/v1/insights/history")).json()) == 1


async def test_schema_failure_retries_once_then_records_error(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki,
    fake_ai: FakeAiProvider,
) -> None:
    scripted_loki.pause_seconds = 3600
    host_id = await _connected_host(authed)
    # Primeira resposta fora do esquema, segunda válida: o retry salva.
    fake_ai.reply("desculpe, não consegui")
    fake_ai.reply(VALID_INSIGHT)
    await _project_with_error(authed, host_id)

    async def has_insight() -> bool:
        return len((await authed.get("/api/v1/insights")).json()) > 0

    await _wait(has_insight, timeout=10, msg="retry não produziu insight")
    assert len(fake_ai.calls) == 2
    assert "não seguiu o formato exigido" in fake_ai.calls[1]["user"]
    calls = (await authed.get("/api/v1/settings/usage/calls")).json()
    assert {c["status"] for c in calls} == {"ok", "error"}
    assert any(c["schema_retry"] for c in calls)


async def test_two_schema_failures_give_up_and_notify(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki,
    fake_ai: FakeAiProvider,
) -> None:
    scripted_loki.pause_seconds = 3600
    host_id = await _connected_host(authed)
    fake_ai.reply(json.dumps({"severity": "altíssima"}))
    fake_ai.reply(json.dumps({"severity": "ainda errado"}))
    await _project_with_error(authed, host_id)

    async def notified() -> bool:
        return any(
            n["type"] == "ai_error" for n in (await authed.get("/api/v1/notifications")).json()
        )

    await _wait(notified, timeout=10, msg="falha de esquema não virou notificação")
    assert (await authed.get("/api/v1/insights")).json() == []
    # O trigger continua registrado como sem análise: nada se perde em silêncio.
    assert len((await authed.get("/api/v1/insights/unanalyzed")).json()) == 1
    calls = (await authed.get("/api/v1/settings/usage/calls")).json()
    assert len(calls) == 2 and all(c["status"] == "error" for c in calls)


async def test_provider_error_notifies_and_keeps_trigger(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki,
    fake_ai: FakeAiProvider,
) -> None:
    scripted_loki.pause_seconds = 3600
    host_id = await _connected_host(authed)
    fake_ai.reply(AiError("O OpenRouter recusou a chave de API.", status=401))
    await _project_with_error(authed, host_id)

    async def notified() -> bool:
        return any(
            n["type"] == "ai_error" for n in (await authed.get("/api/v1/notifications")).json()
        )

    await _wait(notified, timeout=10, msg="erro do provider não virou notificação")
    assert (await authed.get("/api/v1/insights")).json() == []
    assert len((await authed.get("/api/v1/insights/unanalyzed")).json()) == 1
    calls = (await authed.get("/api/v1/settings/usage/calls?only=errors")).json()
    assert "recusou a chave" in calls[0]["error"]
    # Uma única chamada: erro do provider não dispara o retry de esquema.
    assert len(fake_ai.calls) == 1


async def test_rate_limit_pauses_the_ai(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki,
    fake_ai: FakeAiProvider,
) -> None:
    scripted_loki.pause_seconds = 3600
    host_id = await _connected_host(authed)
    fake_ai.reply(RateLimitedError("O OpenRouter recusou por limite de uso.", retry_after=60))
    await _project_with_error(authed, host_id)

    async def paused() -> bool:
        return bool((await authed.get("/api/v1/settings/usage")).json()["paused_providers"])

    await _wait(paused, timeout=10, msg="limite de uso não pausou o provider")
    # Com a IA pausada, uma análise manual não chama o provider de novo.
    before = len(fake_ai.calls)
    inv = (await authed.get(f"/api/v1/hosts/{host_id}/containers")).json()
    api = next(c for c in inv if c["name"] == "api")
    await authed.post(f"/api/v1/projects/{api['id']}/analyze", json={"minutes": 5})
    await asyncio.sleep(0.3)
    assert len(fake_ai.calls) == before


async def test_ai_disabled_leaves_trigger_unanalyzed(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki,
    fake_ai: FakeAiProvider,
) -> None:
    scripted_loki.pause_seconds = 3600
    ai_service.get_runtime().enabled = False  # type: ignore[attr-defined]
    host_id = await _connected_host(authed)
    await _project_with_error(authed, host_id)

    async def unanalyzed() -> bool:
        return len((await authed.get("/api/v1/insights/unanalyzed")).json()) > 0

    await _wait(unanalyzed, timeout=10)
    assert (await authed.get("/api/v1/insights")).json() == []
    assert (await authed.get("/api/v1/settings/usage/calls")).json() == []
    assert fake_ai.calls == []
    # Sem IA não há notificação de erro: não é falha, é escolha.
    assert all(n["type"] != "ai_error" for n in (await authed.get("/api/v1/notifications")).json())


async def test_usage_aggregates(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki,
    fake_ai: FakeAiProvider,
) -> None:
    scripted_loki.pause_seconds = 3600
    host_id = await _connected_host(authed)
    fake_ai.reply(VALID_INSIGHT)
    await _project_with_error(authed, host_id)

    async def has_call() -> bool:
        return (await authed.get("/api/v1/settings/usage")).json()["total"]["calls"] > 0

    await _wait(has_call, timeout=10)
    usage = (await authed.get("/api/v1/settings/usage")).json()
    assert usage["today"]["calls"] == 1 and usage["total"]["calls"] == 1
    assert float(usage["total"]["cost_usd"]) > 0
    assert usage["total"]["input_tokens"] > 0
    assert [b["key"] for b in usage["by_project"]] == ["api"]
    assert [b["key"] for b in usage["by_trigger"]] == ["error"]
    assert [b["key"] for b in usage["by_purpose"]] == ["analyze"]
    assert usage["failures"] == 0 and usage["schema_retries"] == 0
    assert len(usage["by_day"]) == 1


async def test_fallback_to_second_provider(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki: AnalysisManager,
) -> None:
    """O primeiro provider falha, o segundo responde: o insight sai e a chamada fica marcada."""
    primary, secondary = FakeAiProvider(), FakeAiProvider()
    runtime = FakeRuntime(primary, secondary)
    await runtime.install()
    ai_service.set_runtime(runtime)  # type: ignore[arg-type]
    try:
        scripted_loki.pause_seconds = 3600
        host_id = await _connected_host(authed)
        primary.reply(AiError("OpenAI indisponível (HTTP 503).", retryable=True))
        secondary.reply(VALID_INSIGHT)
        await _project_with_error(authed, host_id)

        async def has_insight() -> bool:
            return len((await authed.get("/api/v1/insights")).json()) > 0

        await _wait(has_insight, timeout=10, msg="o fallback não produziu insight")
        assert len(primary.calls) == 1 and len(secondary.calls) == 1

        calls = (await authed.get("/api/v1/settings/usage/calls")).json()
        failed = next(c for c in calls if c["status"] == "error")
        ok = next(c for c in calls if c["status"] == "ok")
        assert failed["attempt"] == 0 and failed["fell_back"] is False
        assert ok["attempt"] == 1 and ok["fell_back"] is True
        assert ok["provider_name"] == "fake-1"

        usage = (await authed.get("/api/v1/settings/usage")).json()
        assert usage["fallbacks"] == 1
        names = {p["name"]: p for p in usage["by_provider"]}
        assert names["fake-0"]["errors"] == 1 and names["fake-0"]["success_rate"] == 0.0
        assert names["fake-1"]["calls"] == 1 and names["fake-1"]["success_rate"] == 1.0
    finally:
        ai_service.set_runtime(None)


async def test_chain_exhausted_notifies_once(
    authed: AsyncClient,
    fake_env: tuple[FakeDocker, FakeSshBackend, str],
    fake_alloy: FakeAlloy,
    scripted_loki: AnalysisManager,
) -> None:
    """Todos os providers falham: uma notificação, nenhum insight, trigger sem análise."""
    first, second = FakeAiProvider(), FakeAiProvider()
    runtime = FakeRuntime(first, second)
    await runtime.install()
    ai_service.set_runtime(runtime)  # type: ignore[arg-type]
    try:
        scripted_loki.pause_seconds = 3600
        host_id = await _connected_host(authed)
        first.reply(AiError("A OpenAI recusou a chave de API.", status=401))
        second.reply(AiError("O Bedrock recusou as credenciais.", status=403))
        await _project_with_error(authed, host_id)

        async def notified() -> bool:
            ns = (await authed.get("/api/v1/notifications")).json()
            return any(n["type"] == "ai_error" for n in ns)

        await _wait(notified, timeout=10, msg="cadeia esgotada não notificou")
        assert (await authed.get("/api/v1/insights")).json() == []
        assert len((await authed.get("/api/v1/insights/unanalyzed")).json()) == 1
        calls = (await authed.get("/api/v1/settings/usage/calls")).json()
        assert len(calls) == 2 and all(c["status"] == "error" for c in calls)
        assert {c["attempt"] for c in calls} == {0, 1}
        # Uma notificação só, no fim da cadeia, não uma por provider.
        ns = [
            n for n in (await authed.get("/api/v1/notifications")).json() if n["type"] == "ai_error"
        ]
        assert len(ns) == 1
    finally:
        ai_service.set_runtime(None)
