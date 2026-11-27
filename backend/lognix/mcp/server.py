"""O servidor MCP, montado em /mcp. Ver ADR 017.

A autenticação é por chave de API no cabeçalho `Authorization`, e cada ferramenta declara o
escopo que exige. O escopo é verificado **na chamada**, não só na conexão: uma chave de leitura
que descobrisse o nome de uma ferramenta de análise não deve conseguir gastar dinheiro com ela.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import AnyHttpUrl

from lognix.config import get_settings
from lognix.db import get_sessionmaker
from lognix.mcp import keys as servico_chaves
from lognix.mcp import tools
from lognix.mcp.models import McpKey, McpScope

log = logging.getLogger(__name__)

#: A chave da requisição em curso, para o registro de uso saber quem chamou.
_chave_atual: ContextVar[McpKey | None] = ContextVar("mcp_chave", default=None)


class ChaveDeApi(TokenVerifier):
    """Valida a chave contra o banco e devolve os escopos dela."""

    async def verify_token(self, token: str) -> AccessToken | None:
        async with get_sessionmaker()() as db:
            registro = await servico_chaves.verificar(db, token)
            if registro is None:
                return None
            _chave_atual.set(registro)
            return AccessToken(
                token=token,
                client_id=str(registro.id),
                scopes=list(registro.scopes or []),
                subject=registro.name,
            )


class EscopoInsuficienteError(Exception):
    """Escopo insuficiente. Vira erro visível para o modelo, com o que falta."""


def _exige(escopo: McpScope) -> None:
    registro = _chave_atual.get()
    concedidos = set(registro.scopes or []) if registro else set()
    # `admin` não implica os outros de propósito: uma chave de automação de custos não deveria
    # poder ler log por tabela. Quem quer tudo marca tudo, e isso fica visível na tela.
    if str(escopo) not in concedidos:
        raise EscopoInsuficienteError(
            f"Esta chave não tem o escopo '{escopo}'. "
            f"Escopos da chave: {', '.join(sorted(concedidos)) or 'nenhum'}."
        )


async def _executar[T](
    nome: str, escopo: McpScope, acao: Callable[..., Awaitable[T]], **kw: Any
) -> T:
    """Envelope de toda ferramenta: confere escopo, mede, registra, traduz erro."""
    comeco = time.perf_counter()
    registro = _chave_atual.get()
    erro: str | None = None
    try:
        _exige(escopo)
        async with get_sessionmaker()() as db:
            return await acao(db, **kw)
    except (tools.ToolError, EscopoInsuficienteError) as exc:
        # O SDK só deixa passar a mensagem de ToolError dele; qualquer outra exceção o modelo
        # recebe como "Error executing tool X", e aí perde justamente a dica que resolveria.
        erro = str(exc)
        raise ToolError(str(exc)) from exc
    except Exception as exc:
        # Falha inesperada também precisa ficar no registro, senão some junto com a resposta.
        erro = f"{type(exc).__name__}: {exc}"
        log.exception("ferramenta MCP falhou", extra={"tool": nome})
        raise
    finally:
        duracao = int((time.perf_counter() - comeco) * 1000)
        try:
            async with get_sessionmaker()() as db:
                anexada = await db.get(McpKey, registro.id) if registro else None
                await servico_chaves.registrar_uso(
                    db, anexada, tool=nome, ok=erro is None, duracao_ms=duracao, erro=erro
                )
        except Exception:
            # Auditoria falhando não pode derrubar a resposta que já foi produzida.
            log.exception("não foi possível registrar a chamada MCP", extra={"tool": nome})


def construir() -> MCPServer:
    base = get_settings().lognix_public_url.rstrip("/")
    servidor = MCPServer(
        name="lognix",
        title="Lognix",
        instructions=(
            "Ferramentas do Lognix, que monitora logs de containers Docker. Use-as para "
            "responder o que aconteceu num serviço: comece por lognix_listar_projetos para "
            "descobrir os nomes, depois lognix_listar_insights para o que o Lognix já "
            "diagnosticou, e lognix_buscar_logs quando precisar das linhas cruas. "
            "As evidências de um insight são linhas reais, não texto gerado."
        ),
        token_verifier=ChaveDeApi(),
        # O SDK só aceita um verificador junto de AuthSettings. Não somos um servidor
        # OAuth: a autenticação é a chave de API no Authorization, e é por isso que
        # validate_token_resource fica desligado — não há `aud` para conferir.
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(base),
            resource_server_url=AnyHttpUrl(f"{base}/mcp"),
            validate_token_resource=False,
        ),
    )

    @servidor.tool(
        name="lognix_listar_hosts",
        description="Máquinas monitoradas pelo Lognix e o estado da conexão com cada uma.",
    )
    async def _hosts() -> list[dict[str, Any]]:
        return await _executar("lognix_listar_hosts", McpScope.leitura, tools.listar_hosts)

    @servidor.tool(
        name="lognix_listar_projetos",
        description=(
            "Containers que o Lognix acompanha, com host, imagem e estado. Comece por aqui: "
            "as outras ferramentas aceitam o nome do projeto que esta devolve."
        ),
    )
    async def _projetos(apenas_monitorados: bool = True) -> list[dict[str, Any]]:
        return await _executar(
            "lognix_listar_projetos",
            McpScope.leitura,
            tools.listar_projetos,
            apenas_monitorados=apenas_monitorados,
        )

    @servidor.tool(
        name="lognix_buscar_logs",
        description=(
            "Linhas de log de um projeto numa janela de tempo, com filtro de texto opcional. "
            "Use quando precisar do texto cru; para o diagnóstico já pronto, prefira "
            "lognix_listar_insights."
        ),
    )
    async def _logs(
        projeto: str, horas: float = 1.0, contendo: str | None = None, limite: int = 100
    ) -> dict[str, Any]:
        return await _executar(
            "lognix_buscar_logs",
            McpScope.leitura,
            tools.buscar_logs,
            projeto=projeto,
            horas=horas,
            contendo=contendo,
            limite=limite,
        )

    @servidor.tool(
        name="lognix_listar_insights",
        description=(
            "Problemas que o Lognix já diagnosticou, do mais recente para o mais antigo. "
            "Cada um traz severidade, resumo e quantas vezes o mesmo problema reapareceu."
        ),
    )
    async def _insights(
        severidade: str | None = None, apenas_abertos: bool = True, limite: int = 20
    ) -> list[dict[str, Any]]:
        return await _executar(
            "lognix_listar_insights",
            McpScope.leitura,
            tools.listar_insights,
            severidade=severidade,
            apenas_abertos=apenas_abertos,
            limite=limite,
        )

    @servidor.tool(
        name="lognix_obter_insight",
        description=(
            "Um insight inteiro: causa provável, ação sugerida e as linhas de log que embasaram "
            "a conclusão. Use para conferir o diagnóstico em vez de aceitá-lo."
        ),
    )
    async def _insight(insight_id: str) -> dict[str, Any]:
        return await _executar(
            "lognix_obter_insight", McpScope.leitura, tools.obter_insight, insight_id=insight_id
        )

    @servidor.tool(
        name="lognix_listar_ocorrencias",
        description=(
            "Momentos em que o Lognix detectou algo digno de análise: erro, evento do Docker ou "
            "anomalia. Inclui as que ficaram sem análise."
        ),
    )
    async def _ocorrencias(
        projeto: str | None = None, horas: float = 24.0, limite: int = 30
    ) -> list[dict[str, Any]]:
        return await _executar(
            "lognix_listar_ocorrencias",
            McpScope.leitura,
            tools.listar_ocorrencias,
            projeto=projeto,
            horas=horas,
            limite=limite,
        )

    @servidor.tool(
        name="lognix_listar_padroes",
        description=(
            "Formas de linha de log que mais se repetem num projeto, agrupadas. Boa primeira "
            "parada para entender o que aquele serviço escreve o tempo todo."
        ),
    )
    async def _padroes(projeto: str, limite: int = 20) -> list[dict[str, Any]]:
        return await _executar(
            "lognix_listar_padroes",
            McpScope.leitura,
            tools.listar_padroes,
            projeto=projeto,
            limite=limite,
        )

    @servidor.tool(
        name="lognix_analisar_agora",
        description=(
            "Roda um ciclo de análise do projeto agora, sobre os últimos minutos, em vez de "
            "esperar o ciclo automático. Devolve as ocorrências detectadas; os insights da IA "
            "aparecem em lognix_listar_insights alguns segundos depois. Uma por minuto por "
            "projeto. Use quando o usuário pedir para olhar o estado de agora."
        ),
    )
    async def _analisar(projeto: str, minutos: float = 15.0) -> dict[str, Any]:
        return await _executar(
            "lognix_analisar_agora",
            McpScope.analise,
            tools.analisar_agora,
            projeto=projeto,
            minutos=minutos,
        )

    @servidor.tool(
        name="lognix_consumo_ia",
        description="Quanto a análise por IA custou no período, no total e por provedor.",
    )
    async def _consumo(dias: int = 7) -> dict[str, Any]:
        return await _executar("lognix_consumo_ia", McpScope.admin, tools.consumo_ia, dias=dias)

    @servidor.tool(
        name="lognix_estado_do_sistema",
        description=(
            "Saúde do próprio Lognix: hosts conectados, ciclos de análise nas últimas 24 horas "
            "e quantas ocorrências ficaram sem análise."
        ),
    )
    async def _estado() -> dict[str, Any]:
        return await _executar("lognix_estado_do_sistema", McpScope.admin, tools.estado_do_sistema)

    return servidor


#: Catálogo para a interface mostrar o que cada escopo libera, sem subir o servidor.
CATALOGO: list[dict[str, str]] = [
    {
        "nome": "lognix_listar_hosts",
        "escopo": "leitura",
        "descricao": "Máquinas e estado da conexão.",
    },
    {
        "nome": "lognix_listar_projetos",
        "escopo": "leitura",
        "descricao": "Containers acompanhados.",
    },
    {
        "nome": "lognix_buscar_logs",
        "escopo": "leitura",
        "descricao": "Linhas de log de um projeto.",
    },
    {
        "nome": "lognix_listar_insights",
        "escopo": "leitura",
        "descricao": "Problemas diagnosticados.",
    },
    {
        "nome": "lognix_obter_insight",
        "escopo": "leitura",
        "descricao": "Um insight com evidências.",
    },
    {"nome": "lognix_listar_ocorrencias", "escopo": "leitura", "descricao": "Detecções do ciclo."},
    {
        "nome": "lognix_listar_padroes",
        "escopo": "leitura",
        "descricao": "Padrões de log de um projeto.",
    },
    {
        "nome": "lognix_analisar_agora",
        "escopo": "analise",
        "descricao": "Dispara um ciclo de análise do projeto agora.",
    },
    {
        "nome": "lognix_consumo_ia",
        "escopo": "admin",
        "descricao": "Custo da IA por período e provedor.",
    },
    {
        "nome": "lognix_estado_do_sistema",
        "escopo": "admin",
        "descricao": "Saúde do próprio Lognix.",
    },
]
