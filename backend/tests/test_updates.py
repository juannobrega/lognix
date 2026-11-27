"""Verificação de atualização. Ver ADR 018.

A consulta ao registro é falsificada por transporte: o teste não pode depender de ter internet,
nem de qual versão está publicada de verdade no GHCR hoje.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient

from lognix.updates import service

ROTA = "/api/v1/system/update"


def registro(tags: list[str] | None = None, *, falha: int | None = None) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        if falha is not None:
            return httpx.Response(falha, text="nope")
        if pedido.url.path == "/token":
            assert pedido.url.params["scope"] == "repository:juannobrega/lognix:pull"
            return httpx.Response(200, json={"token": "t0ken"})
        assert pedido.headers["Authorization"] == "Bearer t0ken"
        return httpx.Response(200, json={"name": "juannobrega/lognix", "tags": tags or []})

    return httpx.MockTransport(responder)


@pytest.fixture(autouse=True)
def _sem_cache() -> None:
    service.limpar_cache()


def test_tupla_compara_numero_nao_texto() -> None:
    """`1.10.0` é maior que `1.9.0`. Comparar texto erra, e já errou neste projeto."""
    assert service.tupla("1.10.0") > service.tupla("1.9.0")  # type: ignore[operator]
    assert service.tupla("v1.2.3") == (1, 2, 3)


def test_tupla_recusa_o_que_nao_e_versao() -> None:
    # A lista do registro traz estas junto das versões.
    for lixo in ("latest", "1", "1.3", "buildcache", "", "1.2.3-rc1"):
        assert service.tupla(lixo) is None


async def test_acha_a_maior_versao_publicada(monkeypatch) -> None:
    monkeypatch.setattr(service, "__version__", "1.2.0")
    r = await service.verificar(transport=registro(["1.9.0", "latest", "1.10.0", "buildcache"]))
    assert r.disponivel == "1.10.0"
    assert r.tem_novidade is True


async def test_na_mesma_versao_nao_ha_novidade(monkeypatch) -> None:
    monkeypatch.setattr(service, "__version__", "1.3.0")
    r = await service.verificar(transport=registro(["1.3.0", "1.2.0", "latest"]))
    assert r.disponivel == "1.3.0"
    assert r.tem_novidade is False


async def test_versao_de_desenvolvimento_nao_vira_novidade(monkeypatch) -> None:
    """`0.0.0` é o placeholder do pyproject fora do release: não é versão para comparar."""
    monkeypatch.setattr(service, "__version__", "não-versionado")
    r = await service.verificar(transport=registro(["1.3.0"]))
    assert r.tem_novidade is False


async def test_registro_fora_do_ar_nao_e_erro(monkeypatch) -> None:
    """Instalação em rede fechada é caso normal: a resposta é "não sei", e a tela não mostra nada."""
    monkeypatch.setattr(service, "__version__", "1.0.0")
    r = await service.verificar(transport=registro(falha=503))
    assert r.disponivel is None
    assert r.tem_novidade is False


async def test_token_vazio_nao_derruba_a_verificacao(monkeypatch) -> None:
    """Registro que responde 200 sem token: trata como indisponível, não como exceção vazando."""
    monkeypatch.setattr(service, "__version__", "1.0.0")

    def sem_token(pedido: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    r = await service.verificar(transport=httpx.MockTransport(sem_token))
    assert r.disponivel is None


async def test_sem_tag_de_versao_nao_invent_nada(monkeypatch) -> None:
    monkeypatch.setattr(service, "__version__", "1.0.0")
    r = await service.verificar(transport=registro(["latest", "buildcache"]))
    assert r.disponivel is None


async def test_cache_evita_consultar_a_cada_abertura_de_tela(monkeypatch) -> None:
    monkeypatch.setattr(service, "__version__", "1.0.0")
    chamadas = {"n": 0}

    def contando(pedido: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        if pedido.url.path == "/token":
            return httpx.Response(200, json={"token": "t"})
        return httpx.Response(200, json={"tags": ["1.1.0"]})

    t = httpx.MockTransport(contando)
    await service.verificar(transport=t, agora=1000.0)
    await service.verificar(transport=t, agora=1000.0 + 3600)
    assert chamadas["n"] == 2, "duas requisições por consulta: token e lista"

    await service.verificar(transport=t, agora=1000.0 + service.CACHE_SEGUNDOS + 1)
    assert chamadas["n"] == 4, "passadas 6 horas, consulta de novo"


# --- rota ---------------------------------------------------------------------------------


async def test_rota_exige_login(client: AsyncClient) -> None:
    assert (await client.get(ROTA)).status_code == 401
    assert (await client.put(ROTA, json={"enabled": True})).status_code == 401


async def test_nasce_desligada_e_nao_consulta_nada(authed: AsyncClient, monkeypatch) -> None:
    """A documentação promete não chamar para fora sem pedido. Desligada, nem consulta."""

    async def explodir(**kw: object) -> None:
        raise AssertionError("não deveria consultar o registro com a verificação desligada")

    monkeypatch.setattr(service, "verificar", explodir)
    corpo = (await authed.get(ROTA)).json()
    assert corpo["enabled"] is False
    assert corpo["available"] is None
    assert corpo["outdated"] is False
    assert corpo["checked_at"] is None
    # Mesmo desligada, a tela mostra a versão rodando e o comando.
    assert corpo["current"]
    assert corpo["command"] == "docker compose pull && docker compose up -d"


async def test_ligar_consulta_na_hora(authed: AsyncClient, monkeypatch) -> None:
    async def falso(**kw: object) -> service.Resultado:
        return service.Resultado(atual="1.0.0", disponivel="1.4.0", verificado_em=1000.0)

    monkeypatch.setattr(service, "verificar", falso)
    corpo = (await authed.put(ROTA, json={"enabled": True})).json()
    assert corpo["enabled"] is True
    assert corpo["available"] == "1.4.0"
    assert corpo["outdated"] is True
    assert corpo["checked_at"] is not None
    assert corpo["changelog_url"].startswith("https://")


async def test_desligar_para_de_consultar(authed: AsyncClient, monkeypatch) -> None:
    async def falso(**kw: object) -> service.Resultado:
        return service.Resultado(atual="1.0.0", disponivel="1.4.0", verificado_em=1000.0)

    monkeypatch.setattr(service, "verificar", falso)
    await authed.put(ROTA, json={"enabled": True})
    corpo = (await authed.put(ROTA, json={"enabled": False})).json()
    assert corpo["enabled"] is False and corpo["available"] is None


async def test_declarada_no_arquivo_nao_muda_pela_tela(authed: AsyncClient) -> None:
    from lognix.settings import config_file

    anterior = config_file.active()
    config_file._ativa = config_file.FileConfig(managed={"updates.check_enabled": True})
    try:
        assert (await authed.get(ROTA)).json()["managed"] is True
        resp = await authed.put(ROTA, json={"enabled": False})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "managed_by_file"
    finally:
        config_file._ativa = anterior
