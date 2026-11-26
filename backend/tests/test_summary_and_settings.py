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
    assert s["enabled"] is False and s["configured"] is False
    assert s["providers"] == 0 and s["providers_ready"] == 0
    assert s["max_input_tokens"] == 12000

    # Sem provedor pronto, ligar é recusado com uma mensagem útil.
    refused = await authed.put("/api/v1/settings/ai", json={"enabled": True})
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "ai_not_configured"
    assert (await authed.get("/api/v1/settings/ai")).json()["enabled"] is False

    # Ativar na criação sem modelo padrão é recusado, e nada é cadastrado pela metade.
    early = await authed.post(
        "/api/v1/settings/ai/providers",
        json={"kind": "openrouter", "name": "OpenRouter", "enabled": True},
    )
    assert early.status_code == 400 and early.json()["error"]["code"] == "provider_not_ready"
    assert (await authed.get("/api/v1/settings/ai")).json()["providers"] == 0

    # Provedor sem modelo padrão conta como cadastrado, mas não entra na cadeia.
    created = (
        await authed.post(
            "/api/v1/settings/ai/providers",
            json={
                "kind": "openrouter",
                "name": "OpenRouter",
                "credentials": {"api_key": "sk-or-segredo-que-nao-pode-vazar"},
            },
        )
    ).json()
    half = (await authed.get("/api/v1/settings/ai")).json()
    assert half["providers"] == 1 and half["providers_ready"] == 0 and half["configured"] is False

    await authed.put(
        f"/api/v1/settings/ai/providers/{created['id']}",
        json={"default_model": "anthropic/claude-sonnet-4.5", "enabled": True},
    )
    saved = (await authed.put("/api/v1/settings/ai", json={"concurrency": 5})).json()
    assert saved["concurrency"] == 5
    # Com um provedor pronto a IA *pode* ser ligada, mas ainda não está.
    assert saved["providers_ready"] == 1
    assert saved["configured"] is True and saved["enabled"] is False and saved["active"] is False
    assert (await authed.get("/api/v1/summary")).json()["ai_enabled"] is False

    on = (await authed.put("/api/v1/settings/ai", json={"enabled": True})).json()
    assert on["enabled"] is True and on["active"] is True

    # A credencial nunca volta pela API, nem aqui, nem no provedor, nem no resumo.
    for path in ("/api/v1/settings/ai", "/api/v1/settings/ai/providers", "/api/v1/summary"):
        assert "sk-or-segredo" not in (await authed.get(path)).text
    assert (await authed.get("/api/v1/summary")).json()["ai_enabled"] is True

    # Desativar o único provedor esvazia a cadeia: o interruptor segue ligado e a IA não roda.
    await authed.put(f"/api/v1/settings/ai/providers/{created['id']}", json={"enabled": False})
    off = (await authed.get("/api/v1/settings/ai")).json()
    assert off["configured"] is False and off["enabled"] is True and off["active"] is False
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

    from lognix.ai.models import AiProviderConfig
    from lognix.db import get_sessionmaker

    await authed.post(
        "/api/v1/settings/ai/providers",
        json={
            "kind": "openai",
            "name": "OpenAI",
            "credentials": {"api_key": "sk-outro-segredo", "organization": "org-lognix"},
        },
    )
    async with get_sessionmaker()() as db:
        row = (await db.execute(select(AiProviderConfig))).scalar_one()
    assert row.credentials_enc is not None
    assert b"sk-outro-segredo" not in row.credentials_enc
    assert b"org-lognix" not in row.credentials_enc
    # O que volta pela API é a lista de chaves preenchidas, não os valores.
    assert row.credential_keys == ["api_key", "organization"]


async def test_legacy_openrouter_key_becomes_a_provider(authed: AsyncClient) -> None:
    """Instalação da 0.9.0 sobe na 1.0.0 sem reconfigurar: a chave única vira um provedor."""
    from lognix.ai.registry import import_legacy_openrouter
    from lognix.db import get_sessionmaker
    from lognix.settings import service

    async with get_sessionmaker()() as db:
        await service.set_value(db, service.AI_API_KEY, "sk-or-chave-antiga")
        await service.set_value(db, service.AI_MODEL, "anthropic/claude-sonnet-4.5")
        await service.set_value(db, service.AI_ENABLED, "true")
        await db.commit()

        provider = await import_legacy_openrouter(db)
        assert provider is not None and provider.kind == "openrouter"
        assert provider.default_model == "anthropic/claude-sonnet-4.5"
        assert provider.enabled is True

        # A configuração antiga sai, o que também impede o import de rodar duas vezes.
        assert await service.get(db, service.AI_API_KEY) is None
        assert await import_legacy_openrouter(db) is None

    listed = (await authed.get("/api/v1/settings/ai/providers")).json()
    assert [p["name"] for p in listed] == ["OpenRouter"]
    assert listed[0]["ready"] is True and listed[0]["credential_keys"] == ["api_key"]
    assert [m["model_id"] for m in listed[0]["models"]] == ["anthropic/claude-sonnet-4.5"]
    # Com a chave migrada, o interruptor que já estava ligado volta a valer.
    assert (await authed.get("/api/v1/settings/ai")).json()["active"] is True


async def test_modelo_padrao_entra_na_lista_de_modelos(authed: AsyncClient) -> None:
    """Apontar o modelo padrão tem que cadastrá-lo, senão o custo fica zerado para sempre.

    Quem não devolve custo na resposta — Anthropic, Bedrock, OpenAI — depende do preço guardado
    na linha do modelo. Sem linha, não há onde guardar preço, e a tela mostrava "0 modelos" ao
    lado de um modelo padrão preenchido.
    """
    criado = (
        await authed.post(
            "/api/v1/settings/ai/providers",
            json={
                "kind": "anthropic",
                "name": "Anthropic",
                "credentials": {"api_key": "sk-ant-x"},
                "default_model": "claude-haiku-5-5",
            },
        )
    ).json()
    assert [m["model_id"] for m in criado["models"]] == ["claude-haiku-5-5"]

    # Trocar o padrão depois cadastra o novo e mantém o antigo, que pode ter preço configurado.
    trocado = (
        await authed.put(
            f"/api/v1/settings/ai/providers/{criado['id']}",
            json={"default_model": "claude-sonnet-5"},
        )
    ).json()
    assert sorted(m["model_id"] for m in trocado["models"]) == [
        "claude-haiku-5-5",
        "claude-sonnet-5",
    ]
