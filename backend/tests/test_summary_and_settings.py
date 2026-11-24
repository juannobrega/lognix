from httpx import AsyncClient

from tests.conftest import FakeAlloy
from tests.fake_docker import FakeDocker
from tests.fake_ssh import FakeSshBackend
from tests.test_containers import _connected_host
from tests.test_events import _mark


async def test_summary_empty_installation(authed: AsyncClient) -> None:
    s = (await authed.get("/api/v1/summary")).json()
    assert s["hosts_total"] == 0 and s["projects_total"] == 0
    assert s["ai_enabled"] is False
    assert s["hosts"] == [] and s["top_projects"] == []
    assert s["lines_24h"] == 0 and s["cycles_24h"] == 0


async def test_summary_with_host_and_project(
    authed: AsyncClient, fake_env: tuple[FakeDocker, FakeSshBackend, str], fake_alloy: FakeAlloy
) -> None:
    host_id = await _connected_host(authed)
    await _mark(authed, host_id, "api")
    s = (await authed.get("/api/v1/summary")).json()
    assert s["hosts_total"] == 1 and s["hosts_connected"] == 1
    assert s["projects_total"] == 1
    assert s["hosts"][0]["name"] == "vm-01" and s["hosts"][0]["monitored"] == 1
    assert [p["name"] for p in s["top_projects"]] == ["api"]
    assert s["top_projects"][0]["host_name"] == "vm-01"
    assert s["notifications_new"] >= 0


async def test_ai_settings_roundtrip(authed: AsyncClient) -> None:
    s = (await authed.get("/api/v1/settings/ai")).json()
    assert s["enabled"] is False and s["configured"] is False and s["has_api_key"] is False
    assert s["provider"] == "openrouter" and s["max_input_tokens"] == 12000

    # Sem chave e sem modelo, ligar é recusado com uma mensagem útil.
    refused = await authed.put("/api/v1/settings/ai", json={"enabled": True})
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "ai_not_configured"
    assert (await authed.get("/api/v1/settings/ai")).json()["enabled"] is False

    saved = (
        await authed.put(
            "/api/v1/settings/ai",
            json={
                "api_key": "sk-or-segredo-que-nao-pode-vazar",
                "model": "anthropic/claude-sonnet-4.5",
                "concurrency": 5,
            },
        )
    ).json()
    assert saved["has_api_key"] is True and saved["model"] == "anthropic/claude-sonnet-4.5"
    assert saved["concurrency"] == 5
    # Com credenciais a IA *pode* ser ligada, mas ainda não está.
    assert saved["configured"] is True and saved["enabled"] is False and saved["active"] is False
    assert (await authed.get("/api/v1/summary")).json()["ai_enabled"] is False

    on = (await authed.put("/api/v1/settings/ai", json={"enabled": True})).json()
    assert on["enabled"] is True and on["active"] is True

    # A chave nunca volta pela API, nem aqui nem no resumo.
    body = (await authed.get("/api/v1/settings/ai")).text
    assert "sk-or-segredo" not in body
    assert "sk-or-segredo" not in (await authed.get("/api/v1/summary")).text
    assert (await authed.get("/api/v1/summary")).json()["ai_enabled"] is True

    # Campo vazio apaga a chave e a IA deixa de estar configurada.
    cleared = (await authed.put("/api/v1/settings/ai", json={"api_key": ""})).json()
    assert cleared["has_api_key"] is False and cleared["configured"] is False
    # Sem credenciais a IA deixa de rodar mesmo com o interruptor ligado.
    assert cleared["enabled"] is True and cleared["active"] is False
    assert (await authed.get("/api/v1/summary")).json()["ai_enabled"] is False


async def test_ai_settings_validation(authed: AsyncClient) -> None:
    assert (await authed.put("/api/v1/settings/ai", json={"concurrency": 0})).status_code == 422
    assert (
        await authed.put("/api/v1/settings/ai", json={"max_input_tokens": 10})
    ).status_code == 422
    assert (
        await AsyncClient(transport=authed._transport, base_url="http://test").get(
            "/api/v1/settings/ai"
        )
    ).status_code == 401


async def test_ai_key_is_encrypted_at_rest(authed: AsyncClient) -> None:
    from sqlalchemy import select

    from lognix.db import get_sessionmaker
    from lognix.settings.models import Setting

    await authed.put("/api/v1/settings/ai", json={"api_key": "sk-or-outro-segredo"})
    async with get_sessionmaker()() as db:
        row = (
            await db.execute(select(Setting).where(Setting.key == "ai.openrouter.api_key"))
        ).scalar_one()
    assert row.value is None and row.value_enc is not None
    assert b"sk-or-outro-segredo" not in row.value_enc
