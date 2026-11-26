"""O frontend servido pela API. Ver ADR 013 e `lognix/api/static.py`.

Estes casos existem porque a troca do nginx por FastAPI é exatamente o tipo de mudança que preserva
o comportamento visível e perde as garantias de borda. Cada um aqui é uma garantia que o nginx dava
e que já quebrou de verdade uma vez.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lognix.api.static import mount_frontend


@pytest.fixture
def build(tmp_path):
    """Um build de frontend de mentira, com a mesma forma que o Vite produz."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Lognix</title>", encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "logo-on-dark.png").write_bytes(b"\x89PNG")
    return tmp_path


@pytest.fixture
async def client(build):
    app = FastAPI()

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    mount_frontend(app, build)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_asset_que_nao_existe_e_404_e_nao_o_index(client: AsyncClient) -> None:
    """A falha mais cara de diagnosticar que um deploy produz.

    Com o index respondendo 200 em lugar de um bundle que saiu na versão anterior, o browser
    recebe HTML onde espera JavaScript, o módulo não parseia, e a tela fica branca sem erro de
    rede nem log no servidor.
    """
    r = await client.get("/assets/index-sumiu.js")
    assert r.status_code == 404
    assert "<!doctype html>" not in r.text.lower()


async def test_asset_com_hash_e_imutavel(client: AsyncClient) -> None:
    r = await client.get("/assets/index-abc123.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_index_revalida_sempre(client: AsyncClient) -> None:
    """Nome fixo e conteúdo novo a cada versão: em cache, nunca descobriria que há versão nova."""
    r = await client.get("/")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"


async def test_arquivo_de_raiz_sem_hash_nao_e_imutavel(client: AsyncClient) -> None:
    """O logo não tem hash no nome: marcá-lo imutável prenderia a troca de arte por um ano."""
    r = await client.get("/logo-on-dark.png")
    assert r.status_code == 200
    assert "immutable" not in r.headers["cache-control"]


async def test_rota_do_react_devolve_o_index(client: AsyncClient) -> None:
    r = await client.get("/settings/providers")
    assert r.status_code == 200
    assert "<!doctype html>" in r.text.lower()


async def test_head_na_pagina_responde(client: AsyncClient) -> None:
    """Quem faz HEAD numa página é verificador de link, proxy e health check, não browser."""
    r = await client.head("/")
    assert r.status_code == 200


async def test_a_api_continua_ganhando_do_coringa(client: AsyncClient) -> None:
    """A rota coringa do frontend engoliria a API inteira se fosse registrada antes."""
    r = await client.get("/api/v1/ping")
    assert r.status_code == 200 and r.json() == {"ok": True}


async def test_cabecalhos_de_seguranca_em_tudo(client: AsyncClient) -> None:
    for caminho in ("/", "/api/v1/ping", "/assets/index-abc123.js"):
        r = await client.get(caminho)
        assert r.headers["x-content-type-options"] == "nosniff", caminho
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"], caminho


async def test_sem_build_a_api_sobe_sozinha(tmp_path) -> None:
    """Em desenvolvimento o frontend roda no Vite: a ausência do build não pode derrubar a API."""
    app = FastAPI()

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    mount_frontend(app, tmp_path / "nao-existe")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        assert (await c.get("/api/v1/ping")).status_code == 200
