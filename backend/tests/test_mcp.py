"""Servidor MCP: chaves, escopos, ferramentas e auditoria. Ver ADR 017.

As chamadas de ferramenta passam pelo protocolo de verdade (cliente oficial do SDK sobre
ASGI), não pelas funções diretamente: quase tudo que pode dar errado aqui — autenticação,
escopo, serialização — mora no caminho que o teste direto pula.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest
from httpx import AsyncClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import select

from lognix.analysis.models import TriggerFired as McpOcorrencia
from lognix.containers.models import Container, ContainerState
from lognix.db import get_sessionmaker
from lognix.hosts.models import Host, HostStatus, SshAuthMethod
from lognix.main import app
from lognix.mcp import keys as servico
from lognix.mcp import tools
from lognix.mcp.http import app_mcp
from lognix.mcp.models import McpCall, McpKey, McpScope
from lognix.mcp.server import CATALOGO, construir

ROTA = "/api/v1/settings/mcp"
#: Precisa casar com LOGNIX_PUBLIC_URL: /mcp valida o cabeçalho Host (ADR 017).
BASE = "http://localhost:8080"


@pytest.fixture
async def db() -> AsyncIterator:
    async with get_sessionmaker()() as sessao:
        yield sessao


@pytest.fixture(scope="session")
async def mcp_vivo() -> AsyncIterator[None]:
    """Sobe o ciclo de vida que o Mount não propaga.

    Escopo de sessão porque o gerenciador de sessões do SDK só aceita um `run()` por
    instância, e numa tarefa própria porque o grupo de tarefas do anyio exige sair no
    mesmo contexto em que entrou — o que a desmontagem de fixture não garante.
    """
    alvo = app_mcp()
    pronto, parar = asyncio.Event(), asyncio.Event()

    async def servir() -> None:
        async with alvo.router.lifespan_context(alvo):
            pronto.set()
            await parar.wait()

    tarefa = asyncio.create_task(servir())
    await pronto.wait()
    yield
    parar.set()
    await tarefa


@asynccontextmanager
async def sessao_mcp(chave: str | None) -> AsyncIterator[ClientSession]:
    cabecalhos = {"Authorization": f"Bearer {chave}"} if chave else {}
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url=BASE, headers=cabecalhos
    ) as http:
        async with streamable_http_client(f"{BASE}/mcp", http_client=http) as (
            leitura,
            escrita,
            *_,
        ):
            async with ClientSession(leitura, escrita) as sessao:
                await sessao.initialize()
                yield sessao


async def _chave(db, *escopos: McpScope, nome: str = "teste") -> str:
    _, segredo = await servico.criar(db, nome=nome, escopos=list(escopos or [McpScope.leitura]))
    await db.commit()
    return segredo


@pytest.fixture
async def projeto(db) -> Container:
    host = Host(
        id=uuid.uuid4(),
        name="vm-01",
        address="10.0.0.1",
        ssh_port=22,
        ssh_user="deploy",
        ssh_auth_method=SshAuthMethod.password,
        status=HostStatus.connected,
    )
    c = Container(
        id=uuid.uuid4(),
        host_id=host.id,
        docker_id="abc",
        name="api",
        image="api:1",
        labels={},
        env={},
        state=ContainerState.running,
        monitored=True,
    )
    db.add_all([host, c])
    await db.commit()
    return c


# --- chaves ------------------------------------------------------------------------------


def test_prefixo_identifica_sem_revelar() -> None:
    chave, prefixo = servico.gerar()
    assert chave.startswith(servico.PREFIXO)
    assert chave.startswith(prefixo)
    # O prefixo é curto de propósito: serve para achar a linha, não para adivinhar a chave.
    assert len(prefixo) < len(chave) / 2


async def test_chave_nao_fica_em_claro_no_banco(db) -> None:
    registro, segredo = await servico.criar(db, nome="k", escopos=[McpScope.leitura])
    await db.commit()
    assert segredo not in registro.key_hash
    assert registro.key_hash.startswith("$argon2")


async def test_verificar_aceita_a_certa_e_recusa_o_resto(db) -> None:
    segredo = await _chave(db, McpScope.leitura)
    assert await servico.verificar(db, segredo) is not None
    assert await servico.verificar(db, segredo + "x") is None
    assert await servico.verificar(db, "lgxmcp_naoexiste") is None
    assert await servico.verificar(db, "sem-prefixo") is None


async def test_verificar_recusa_desativada_e_vencida(db) -> None:
    desativada, s1 = await servico.criar(db, nome="off", escopos=[McpScope.leitura])
    desativada.enabled = False
    _, s2 = await servico.criar(
        db,
        nome="velha",
        escopos=[McpScope.leitura],
        expira_em=datetime.now(UTC) - timedelta(seconds=1),
    )
    await db.commit()
    assert await servico.verificar(db, s1) is None
    assert await servico.verificar(db, s2) is None


# --- rotas de gerenciamento --------------------------------------------------------------


async def test_rotas_exigem_login(client: AsyncClient) -> None:
    for metodo, caminho in [
        ("get", ROTA),
        ("get", f"{ROTA}/keys"),
        ("post", f"{ROTA}/keys"),
        ("get", f"{ROTA}/calls"),
    ]:
        resp = await getattr(client, metodo)(caminho)
        assert resp.status_code == 401, caminho


async def test_info_descreve_conexao_escopos_e_ferramentas(authed: AsyncClient) -> None:
    corpo = (await authed.get(ROTA)).json()
    assert corpo["url"].endswith("/mcp")
    assert {e["nome"] for e in corpo["scopes"]} == {"leitura", "analise", "admin"}
    # Sem o risco descrito, ninguém decide escopo com consciência do que a chave libera.
    assert all(e["risco"] for e in corpo["scopes"])
    assert len(corpo["tools"]) == len(CATALOGO)


async def test_catalogo_bate_com_as_ferramentas_registradas() -> None:
    """O catálogo é escrito à mão; sem esta checagem ele mente para a interface."""
    registradas = {f.name for f in await construir().list_tools()}
    assert {f["nome"] for f in CATALOGO} == registradas


async def test_criar_devolve_o_segredo_uma_unica_vez(authed: AsyncClient) -> None:
    criada = await authed.post(
        f"{ROTA}/keys", json={"name": "cli", "scopes": ["leitura", "analise"]}
    )
    assert criada.status_code == 201, criada.text
    corpo = criada.json()
    assert corpo["secret"].startswith(corpo["prefix"])
    assert corpo["scopes"] == ["analise", "leitura"]

    listadas = (await authed.get(f"{ROTA}/keys")).json()
    assert [k["prefix"] for k in listadas] == [corpo["prefix"]]
    assert listadas[0]["secret"] is None
    assert corpo["secret"] not in (await authed.get(f"{ROTA}/keys")).text


async def test_criar_exige_pelo_menos_um_escopo(authed: AsyncClient) -> None:
    resp = await authed.post(f"{ROTA}/keys", json={"name": "vazia", "scopes": []})
    assert resp.status_code == 422


async def test_expiracao_em_dias_vira_data(authed: AsyncClient) -> None:
    corpo = (
        await authed.post(
            f"{ROTA}/keys", json={"name": "curta", "scopes": ["leitura"], "expires_in_days": 30}
        )
    ).json()
    prazo = datetime.fromisoformat(corpo["expires_at"])
    faltam = (prazo - datetime.now(UTC)).total_seconds() / 86400
    assert 29.9 < faltam <= 30


async def test_atualizar_escopos_e_desativar(authed: AsyncClient) -> None:
    criada = (await authed.post(f"{ROTA}/keys", json={"name": "k", "scopes": ["admin"]})).json()
    resp = await authed.put(
        f"{ROTA}/keys/{criada['id']}", json={"scopes": ["leitura"], "enabled": False}
    )
    assert resp.status_code == 200
    assert resp.json()["scopes"] == ["leitura"]
    assert resp.json()["enabled"] is False


async def test_revogar_apaga(authed: AsyncClient) -> None:
    criada = (await authed.post(f"{ROTA}/keys", json={"name": "k", "scopes": ["leitura"]})).json()
    assert (await authed.delete(f"{ROTA}/keys/{criada['id']}")).status_code == 204
    assert (await authed.get(f"{ROTA}/keys")).json() == []
    assert (await authed.delete(f"{ROTA}/keys/{criada['id']}")).status_code == 404


async def test_chave_revogada_para_de_autenticar(authed: AsyncClient, db) -> None:
    criada = (await authed.post(f"{ROTA}/keys", json={"name": "k", "scopes": ["leitura"]})).json()
    assert await servico.verificar(db, criada["secret"]) is not None
    await authed.delete(f"{ROTA}/keys/{criada['id']}")
    assert await servico.verificar(db, criada["secret"]) is None


# --- protocolo ---------------------------------------------------------------------------


async def test_sem_chave_o_mcp_recusa(mcp_vivo: None) -> None:
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=BASE) as http:
        resp = await http.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert resp.status_code == 401
    assert "Bearer" in resp.headers.get("www-authenticate", "")


async def test_chave_invalida_o_mcp_recusa(mcp_vivo: None) -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url=BASE,
        headers={"Authorization": "Bearer lgxmcp_qualquer"},
    ) as http:
        resp = await http.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert resp.status_code == 401


async def test_host_desconhecido_e_recusado(mcp_vivo: None, db) -> None:
    """Proteção contra DNS rebinding: o endereço de fora tem que ser o que foi configurado."""
    chave = await _chave(db, McpScope.leitura)
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url="http://invasor.exemplo",
        headers={"Authorization": f"Bearer {chave}"},
    ) as http:
        resp = await http.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert resp.status_code == 421


async def test_lista_ferramentas_pelo_protocolo(mcp_vivo: None, db) -> None:
    chave = await _chave(db, McpScope.leitura)
    async with sessao_mcp(chave) as sessao:
        nomes = {f.name for f in (await sessao.list_tools()).tools}
    assert nomes == {f["nome"] for f in CATALOGO}


async def test_ferramenta_devolve_dados_e_registra_auditoria(
    mcp_vivo: None, db, projeto: Container
) -> None:
    chave = await _chave(db, McpScope.leitura, nome="cli")
    async with sessao_mcp(chave) as sessao:
        resultado = await sessao.call_tool("lognix_listar_projetos", {})
    assert resultado.is_error is False
    assert "api" in resultado.content[0].text

    chamadas = (await db.execute(select(McpCall))).scalars().all()
    assert [(c.tool, c.ok, c.key_name) for c in chamadas] == [
        ("lognix_listar_projetos", True, "cli")
    ]
    registro = (await db.execute(select(McpKey))).scalars().one()
    assert registro.calls == 1
    assert registro.last_used_at is not None


async def test_escopo_insuficiente_bloqueia_e_fica_registrado(mcp_vivo: None, db) -> None:
    chave = await _chave(db, McpScope.leitura)
    async with sessao_mcp(chave) as sessao:
        resultado = await sessao.call_tool("lognix_estado_do_sistema", {})
    assert resultado.is_error is True
    assert "admin" in resultado.content[0].text  # a mensagem tem que dizer o que falta

    chamada = (await db.execute(select(McpCall))).scalars().one()
    assert chamada.ok is False
    assert chamada.tool == "lognix_estado_do_sistema"


async def test_admin_nao_implica_leitura(mcp_vivo: None, db) -> None:
    """Escopo largo por herança é o jeito mais fácil de uma chave vazada ler tudo."""
    chave = await _chave(db, McpScope.admin)
    async with sessao_mcp(chave) as sessao:
        assert (await sessao.call_tool("lognix_estado_do_sistema", {})).is_error is False
        assert (await sessao.call_tool("lognix_listar_projetos", {})).is_error is True


async def test_projeto_inexistente_volta_como_erro_do_modelo(mcp_vivo: None, db) -> None:
    chave = await _chave(db, McpScope.leitura)
    async with sessao_mcp(chave) as sessao:
        resultado = await sessao.call_tool("lognix_buscar_logs", {"projeto": "nao-existe"})
    assert resultado.is_error is True
    assert "lognix_listar_projetos" in resultado.content[0].text


async def test_analisar_agora_exige_o_escopo_de_analise(
    mcp_vivo: None, db, projeto: Container
) -> None:
    chave = await _chave(db, McpScope.leitura)
    async with sessao_mcp(chave) as sessao:
        resultado = await sessao.call_tool("lognix_analisar_agora", {"projeto": "api"})
    assert resultado.is_error is True
    assert "analise" in resultado.content[0].text


async def test_analisar_agora_respeita_o_limite_da_interface(
    mcp_vivo: None, db, projeto: Container
) -> None:
    """O limite é compartilhado: entrar pelo MCP não dá uma cota extra de análise."""
    from lognix.analysis import manual

    manual.marcar(projeto.id)
    chave = await _chave(db, McpScope.analise)
    async with sessao_mcp(chave) as sessao:
        resultado = await sessao.call_tool("lognix_analisar_agora", {"projeto": "api"})
    assert resultado.is_error is True
    assert "lognix_listar_insights" in resultado.content[0].text


async def test_rota_de_chamadas_mostra_o_historico(
    authed: AsyncClient, mcp_vivo: None, db, projeto: Container
) -> None:
    chave = await _chave(db, McpScope.leitura, nome="cli")
    async with sessao_mcp(chave) as sessao:
        await sessao.call_tool("lognix_listar_projetos", {})
    linhas = (await authed.get(f"{ROTA}/calls")).json()
    assert [x["tool"] for x in linhas] == ["lognix_listar_projetos"]
    assert linhas[0]["key_name"] == "cli"


# --- ferramentas, uma a uma ---------------------------------------------------------------
#
# O caminho pelo protocolo cobre autenticação e escopo; aqui o que se confere é a consulta de
# cada ferramenta. Uma query errada só apareceria na frente de um modelo, em produção.


@pytest.fixture
async def cenario(db, projeto: Container) -> Container:
    """Um projeto com padrão, ciclo, ocorrência, insight e chamada de IA."""
    from decimal import Decimal

    from lognix.ai.models import AiCall, AiCallStatus, AiPurpose, Insight, InsightStatus, Severity
    from lognix.analysis.models import AnalysisRun, LogLevel, Pattern, RunStatus, TriggerType

    agora = datetime.now(UTC)
    db.add(
        Pattern(
            container_id=projeto.id,
            template="ERROR db down: <*>",
            level=LogLevel.error,
            count_total=12,
            sample="ERROR db down: connection refused",
        )
    )
    db.add(
        AnalysisRun(
            container_id=projeto.id,
            window_start=agora - timedelta(minutes=1),
            window_end=agora,
            status=RunStatus.ok,
            lines_count=40,
            error_lines_count=3,
        )
    )
    ocorrencia = McpOcorrencia(
        id=uuid.uuid4(),
        container_id=projeto.id,
        type=TriggerType.error,
        reason={},
        fired_at=agora,
        window_start=agora - timedelta(minutes=1),
        window_end=agora,
        sample_lines=[{"line": "ERROR db down"}],
        note="3 linhas de erro",
    )
    db.add(ocorrencia)
    await db.flush()
    insight = Insight(
        container_id=projeto.id,
        trigger_id=ocorrencia.id,
        dedupe_key="error:db",
        occurrences=2,
        last_seen_at=agora,
        severity=Severity.high,
        title="Banco inacessível",
        summary="O serviço perdeu a conexão com o Postgres.",
        probable_cause="Postgres reiniciou.",
        suggested_action="Conferir o container do banco.",
        confidence=0.9,
        needs_code=False,
        evidence=[{"line": "ERROR db down: connection refused"}],
        sent_context="",
        status=InsightStatus.new,
    )
    db.add(insight)
    db.add(
        AiCall(
            container_id=projeto.id,
            provider="openrouter",
            provider_name="OpenRouter",
            model="anthropic/claude-sonnet-4.5",
            purpose=AiPurpose.analyze,
            input_tokens=1200,
            output_tokens=300,
            cost_usd=Decimal("0.0075"),
            latency_ms=900,
            status=AiCallStatus.ok,
        )
    )
    await db.commit()
    return projeto


async def test_listar_hosts_mostra_estado_da_conexao(db, cenario: Container) -> None:
    linhas = await tools.listar_hosts(db)
    assert [(h["nome"], h["estado"]) for h in linhas] == [("vm-01", "connected")]


async def test_listar_projetos_traz_host_e_imagem(db, cenario: Container) -> None:
    linhas = await tools.listar_projetos(db)
    assert linhas[0]["nome"] == "api"
    assert linhas[0]["host"] == "vm-01"
    assert linhas[0]["imagem"] == "api:1"


async def test_projeto_aceita_nome_ou_id(db, cenario: Container) -> None:
    """O modelo quase sempre tem o nome, não o uuid."""
    por_nome = await tools.listar_padroes(db, projeto="api")
    por_id = await tools.listar_padroes(db, projeto=str(cenario.id))
    assert por_nome == por_id
    assert por_nome[0]["template"] == "ERROR db down: <*>"


async def test_listar_insights_e_obter_um(db, cenario: Container) -> None:
    lista = await tools.listar_insights(db)
    assert [i["titulo"] for i in lista] == ["Banco inacessível"]
    inteiro = await tools.obter_insight(db, insight_id=lista[0]["id"])
    assert inteiro["causa_provavel"] == "Postgres reiniciou."
    # Evidência é linha real de log, não texto gerado: é o que sustenta o diagnóstico.
    assert inteiro["evidencias"][0]["line"].startswith("ERROR db down")


async def test_obter_insight_recusa_id_invalido(db, cenario: Container) -> None:
    with pytest.raises(tools.ToolError):
        await tools.obter_insight(db, insight_id="nao-e-uuid")


async def test_listar_insights_filtra_por_severidade(db, cenario: Container) -> None:
    assert await tools.listar_insights(db, severidade="high")
    assert await tools.listar_insights(db, severidade="low") == []


async def test_listar_ocorrencias_diz_se_foi_analisada(db, cenario: Container) -> None:
    linhas = await tools.listar_ocorrencias(db, projeto="api")
    assert linhas[0]["tipo"] == "error"
    assert linhas[0]["motivo"] == "3 linhas de erro"
    assert linhas[0]["analisada"] is False


async def test_consumo_ia_soma_custo_e_tokens(db, cenario: Container) -> None:
    resumo = await tools.consumo_ia(db, dias=7)
    assert float(resumo["custo_usd"]) == 0.0075
    assert resumo["chamadas"] == 1
    assert resumo["por_provedor"][0]["provedor"] == "OpenRouter"


async def test_estado_do_sistema_conta_hosts_e_ciclos(db, cenario: Container) -> None:
    estado = await tools.estado_do_sistema(db)
    assert estado["hosts"] == {"total": 1, "conectados": 1}
    assert estado["ciclos_24h"] == 1
    assert estado["ocorrencias_sem_analise"] == 1


async def test_buscar_logs_devolve_linhas_com_horario(db, cenario: Container, monkeypatch) -> None:
    from lognix.loki.client import LogLine

    class LokiFalso:
        def __init__(self, *a: Any, **k: Any) -> None:
            self.consultas: list[str] = []

        async def query_range(self, seletor: str, **kw: Any) -> list[LogLine]:
            self.consultas.append(seletor)
            return [LogLine(ts_ns=1_700_000_000_000_000_000, line="ERROR db down", labels={})]

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(tools, "LokiClient", LokiFalso)
    saida = await tools.buscar_logs(db, projeto="api", horas=2, contendo="ERROR", limite=10)
    assert saida["projeto"] == "api"
    assert saida["total"] == 1
    assert saida["linhas"][0]["texto"] == "ERROR db down"
    # A hora vai em ISO: nanossegundo do Loki não é algo que o modelo saiba interpretar.
    assert saida["linhas"][0]["em"].startswith("2023-")


async def test_buscar_logs_respeita_o_teto_de_linhas(db, cenario: Container, monkeypatch) -> None:
    pedidos: dict[str, Any] = {}

    class LokiFalso:
        def __init__(self, *a: Any, **k: Any) -> None:
            pass

        async def query_range(self, seletor: str, **kw: Any) -> list[Any]:
            pedidos.update(kw)
            return []

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(tools, "LokiClient", LokiFalso)
    await tools.buscar_logs(db, projeto="api", limite=10_000)
    assert pedidos["limit"] == tools.MAX_LINHAS


async def test_atualizar_so_o_nome_mantem_os_escopos(authed: AsyncClient) -> None:
    criada = (
        await authed.post(f"{ROTA}/keys", json={"name": "k", "scopes": ["leitura", "admin"]})
    ).json()
    resp = await authed.put(f"{ROTA}/keys/{criada['id']}", json={"name": "renomeada"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "renomeada"
    assert resp.json()["scopes"] == ["admin", "leitura"]


async def test_atualizar_chave_inexistente_da_404(authed: AsyncClient) -> None:
    resp = await authed.put(f"{ROTA}/keys/{uuid.uuid4()}", json={"name": "x"})
    assert resp.status_code == 404


async def test_endereco_sem_barra_final_atende_direto(mcp_vivo: None, db) -> None:
    """A tela mostra /mcp; um 307 aqui mataria a sessão, porque POST redirecionado não repete."""
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=BASE) as http:
        resp = await http.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert resp.status_code == 401, resp.status_code


def test_host_coringa_desliga_a_checagem(monkeypatch) -> None:
    """Quem publica o Lognix por vários nomes atrás de proxy precisa de uma saída."""
    from lognix.config import get_settings
    from lognix.mcp.http import _seguranca

    monkeypatch.setenv("LOGNIX_MCP_ALLOWED_HOSTS", "*")
    get_settings.cache_clear()
    try:
        assert _seguranca().enable_dns_rebinding_protection is False
    finally:
        monkeypatch.delenv("LOGNIX_MCP_ALLOWED_HOSTS")
        get_settings.cache_clear()


async def test_analisar_agora_roda_o_ciclo_e_devolve_as_ocorrencias(
    db, cenario: Container, monkeypatch
) -> None:
    from lognix.loki.client import LogLine

    agora = int(datetime.now(UTC).timestamp() * 1e9)

    class LokiFalso:
        def __init__(self, *a: Any, **k: Any) -> None:
            pass

        async def query_range(self, seletor: str, **kw: Any) -> list[LogLine]:
            return [
                LogLine(ts_ns=agora, line="ERROR db down: connection refused", labels={}),
                LogLine(ts_ns=agora, line="user 1 logged in", labels={}),
            ]

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(tools, "LokiClient", LokiFalso)
    saida = await tools.analisar_agora(db, projeto="api", minutos=5)
    assert saida["projeto"] == "api"
    assert saida["linhas_analisadas"] == 2
    assert saida["linhas_com_erro"] == 1
    assert [o["tipo"] for o in saida["ocorrencias"]] == ["manual"]
    assert saida["ocorrencias"][0]["analisada"] is False
