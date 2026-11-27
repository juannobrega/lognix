"""As ferramentas que o servidor MCP expõe. Ver ADR 017.

Cada ferramenta declara o escopo que exige. A descrição importa tanto quanto o código: é por ela
que o modelo decide se aquela ferramenta responde à pergunta que ele tem na mão, e uma descrição
vaga produz chamada errada ou nenhuma chamada.

Nada aqui escreve no host monitorado, e nada devolve credencial.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.ai.models import AiCall, Insight, InsightStatus, Severity
from lognix.analysis.models import AnalysisRun, Pattern, TriggerFired
from lognix.containers.models import Container
from lognix.hosts.models import Host
from lognix.loki.client import LokiClient, selector
from lognix.mcp.models import McpScope

MAX_LINHAS = 300
MAX_ITENS = 100


class ToolError(Exception):
    """Erro que o modelo deve ver: argumento inválido ou recurso inexistente."""


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    escopo: McpScope
    descricao: str


async def _container(db: AsyncSession, projeto: str) -> Container:
    """Aceita o uuid ou o nome. O modelo quase sempre tem o nome, não o id."""
    try:
        alvo = uuid.UUID(projeto)
        achado = await db.get(Container, alvo)
    except ValueError:
        achado = (
            (
                await db.execute(
                    select(Container).where(Container.name == projeto).order_by(Container.name)
                )
            )
            .scalars()
            .first()
        )
    if achado is None:
        raise ToolError(
            f"Projeto '{projeto}' não encontrado. Use lognix_listar_projetos para ver os nomes."
        )
    return achado


def _janela(horas: float) -> tuple[datetime, datetime]:
    fim = datetime.now(UTC)
    return fim - timedelta(hours=max(0.1, min(horas, 24 * 16))), fim


async def listar_hosts(db: AsyncSession) -> list[dict[str, Any]]:
    linhas = (await db.execute(select(Host).order_by(Host.name))).scalars()
    return [
        {
            "id": str(h.id),
            "nome": h.name,
            "endereco": h.address,
            "estado": str(h.status),
            "ultimo_erro": h.last_error,
        }
        for h in linhas
        if str(h.status) != "removed"
    ]


async def listar_projetos(
    db: AsyncSession, *, apenas_monitorados: bool = True
) -> list[dict[str, Any]]:
    stmt = select(Container, Host).join(Host, Host.id == Container.host_id).order_by(Container.name)
    if apenas_monitorados:
        stmt = stmt.where(Container.monitored.is_(True))
    return [
        {
            "id": str(c.id),
            "nome": c.name,
            "host": h.name,
            "imagem": c.image,
            "estado": str(c.state),
            "monitorado": c.monitored,
        }
        for c, h in (await db.execute(stmt)).all()
    ]


async def buscar_logs(
    db: AsyncSession,
    *,
    projeto: str,
    horas: float = 1.0,
    contendo: str | None = None,
    limite: int = 100,
) -> dict[str, Any]:
    alvo = await _container(db, projeto)
    inicio, fim = _janela(horas)
    cliente = LokiClient()
    try:
        linhas = await cliente.query_range(
            selector(alvo.id, text=contendo),
            start_ns=int(inicio.timestamp() * 1e9),
            end_ns=int(fim.timestamp() * 1e9),
            limit=max(1, min(limite, MAX_LINHAS)),
        )
    finally:
        await cliente.aclose()
    return {
        "projeto": alvo.name,
        "janela": {"de": inicio.isoformat(), "ate": fim.isoformat()},
        "total": len(linhas),
        "linhas": [
            {
                "em": datetime.fromtimestamp(int(linha.ts_ns) / 1e9, tz=UTC).isoformat(),
                "texto": linha.line,
            }
            for linha in linhas
        ],
    }


async def listar_insights(
    db: AsyncSession,
    *,
    severidade: str | None = None,
    apenas_abertos: bool = True,
    limite: int = 20,
) -> list[dict[str, Any]]:
    stmt = (
        select(Insight, Container)
        .join(Container, Container.id == Insight.container_id)
        .order_by(Insight.created_at.desc())
        .limit(max(1, min(limite, MAX_ITENS)))
    )
    if apenas_abertos:
        stmt = stmt.where(Insight.status == InsightStatus.new)
    if severidade:
        try:
            stmt = stmt.where(Insight.severity == Severity(severidade))
        except ValueError as exc:
            validos = ", ".join(s.value for s in Severity)
            raise ToolError(f"Severidade '{severidade}' não existe. Use: {validos}.") from exc
    return [
        {
            "id": str(i.id),
            "projeto": c.name,
            "severidade": str(i.severity),
            "titulo": i.title,
            "resumo": i.summary,
            "ocorrencias": i.occurrences,
            "visto_por_ultimo": i.last_seen_at.isoformat() if i.last_seen_at else None,
            "em": i.created_at.isoformat(),
        }
        for i, c in (await db.execute(stmt)).all()
    ]


async def obter_insight(db: AsyncSession, *, insight_id: str) -> dict[str, Any]:
    try:
        alvo = await db.get(Insight, uuid.UUID(insight_id))
    except ValueError as exc:
        raise ToolError(f"'{insight_id}' não é um id válido.") from exc
    if alvo is None:
        raise ToolError("Insight não encontrado.")
    container = await db.get(Container, alvo.container_id)
    return {
        "id": str(alvo.id),
        "projeto": container.name if container else None,
        "severidade": str(alvo.severity),
        "titulo": alvo.title,
        "resumo": alvo.summary,
        "causa_provavel": alvo.probable_cause,
        "acao_sugerida": alvo.suggested_action,
        "confianca": float(alvo.confidence),
        "ocorrencias": alvo.occurrences,
        # As evidências são as linhas reais que embasaram a conclusão: é o que permite conferir
        # em vez de acreditar.
        "evidencias": alvo.evidence,
        "contexto_cortado": alvo.context_truncated,
        "em": alvo.created_at.isoformat(),
    }


async def listar_ocorrencias(
    db: AsyncSession, *, projeto: str | None = None, horas: float = 24.0, limite: int = 30
) -> list[dict[str, Any]]:
    inicio, _ = _janela(horas)
    stmt = (
        select(TriggerFired, Container)
        .join(Container, Container.id == TriggerFired.container_id)
        .where(TriggerFired.fired_at >= inicio)
        .order_by(TriggerFired.fired_at.desc())
        .limit(max(1, min(limite, MAX_ITENS)))
    )
    if projeto:
        alvo = await _container(db, projeto)
        stmt = stmt.where(TriggerFired.container_id == alvo.id)
    return [
        {
            "id": str(t.id),
            "projeto": c.name,
            "tipo": str(t.type),
            "motivo": t.note,
            "em": t.fired_at.isoformat(),
            "analisada": t.insight_id is not None,
        }
        for t, c in (await db.execute(stmt)).all()
    ]


async def listar_padroes(
    db: AsyncSession, *, projeto: str, limite: int = 20
) -> list[dict[str, Any]]:
    alvo = await _container(db, projeto)
    stmt = (
        select(Pattern)
        .where(Pattern.container_id == alvo.id)
        .order_by(Pattern.count_total.desc())
        .limit(max(1, min(limite, MAX_ITENS)))
    )
    return [
        {
            "template": p.template,
            "ocorrencias": p.count_total,
            "nivel": str(p.level),
            "ignorado": p.ignored,
            "visto_por_ultimo": p.last_seen_at.isoformat() if p.last_seen_at else None,
        }
        for p in (await db.execute(stmt)).scalars()
    ]


async def consumo_ia(db: AsyncSession, *, dias: int = 7) -> dict[str, Any]:
    desde = datetime.now(UTC) - timedelta(days=max(1, min(dias, 90)))
    total, chamadas, entrada, saida = (
        await db.execute(
            select(
                func.coalesce(func.sum(AiCall.cost_usd), 0),
                func.count(),
                func.coalesce(func.sum(AiCall.input_tokens), 0),
                func.coalesce(func.sum(AiCall.output_tokens), 0),
            ).where(AiCall.created_at >= desde)
        )
    ).one()
    por_provedor = (
        await db.execute(
            select(AiCall.provider_name, func.count(), func.coalesce(func.sum(AiCall.cost_usd), 0))
            .where(AiCall.created_at >= desde)
            .group_by(AiCall.provider_name)
        )
    ).all()
    return {
        "dias": dias,
        "custo_usd": str(total),
        "chamadas": int(chamadas),
        "tokens_entrada": int(entrada),
        "tokens_saida": int(saida),
        "por_provedor": [
            {"provedor": nome or "—", "chamadas": int(n), "custo_usd": str(custo)}
            for nome, n, custo in por_provedor
        ],
    }


async def estado_do_sistema(db: AsyncSession) -> dict[str, Any]:
    desde = datetime.now(UTC) - timedelta(hours=24)
    hosts = list((await db.execute(select(Host))).scalars())
    ciclos, falhas = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(AnalysisRun.status == "failed"),
            ).where(AnalysisRun.window_end >= desde)
        )
    ).one()
    sem_analise = (
        await db.execute(
            select(func.count()).select_from(TriggerFired).where(TriggerFired.insight_id.is_(None))
        )
    ).scalar()
    return {
        "hosts": {
            "total": len([h for h in hosts if str(h.status) != "removed"]),
            "conectados": len([h for h in hosts if str(h.status) == "connected"]),
        },
        "ciclos_24h": int(ciclos),
        "ciclos_com_falha_24h": int(falhas),
        "ocorrencias_sem_analise": int(sem_analise or 0),
    }


async def analisar_agora(
    db: AsyncSession, *, projeto: str, minutos: float = 15.0
) -> dict[str, Any]:
    """Roda um ciclo de análise agora, como o botão da interface. Exige o escopo `analise`.

    O limite é o mesmo da tela — uma por minuto por projeto — e de propósito compartilhado:
    um cliente MCP não deveria ganhar uma cota extra só por entrar por outra porta.
    """
    from lognix.analysis import manual
    from lognix.analysis.cycle import cycle_lock, run_cycle
    from lognix.analysis.models import RunStatus

    alvo = await _container(db, projeto)
    falta = manual.espera(alvo.id)
    if falta > 0:
        raise ToolError(
            f"'{alvo.name}' foi analisado agora há pouco. Tente em {int(falta) + 1}s, ou use "
            "lognix_listar_insights para ver o que a última análise achou."
        )
    manual.marcar(alvo.id)
    fim = datetime.now(UTC)
    inicio = fim - timedelta(minutes=max(1.0, min(minutos, 180.0)))
    cliente = LokiClient()
    try:
        async with cycle_lock(alvo.id):
            # fired_by fica nulo: quem disparou foi uma chave, não uma pessoa. A chave está
            # no registro de chamadas MCP, que é onde se procura por isso.
            resultado = await run_cycle(
                db, cliente, alvo, window_start=inicio, window_end=fim, manual=True
            )
    finally:
        await cliente.aclose()
    if resultado.run.status == RunStatus.failed:
        raise ToolError(resultado.run.error or "O ciclo falhou ao consultar o Loki.")
    return {
        "projeto": alvo.name,
        "janela": {"de": inicio.isoformat(), "ate": fim.isoformat()},
        "linhas_analisadas": resultado.run.lines_count,
        "linhas_com_erro": resultado.run.error_lines_count,
        "ocorrencias": [
            {
                "id": str(t.id),
                "tipo": str(t.type),
                "motivo": t.note,
                "analisada": t.insight_id is not None,
            }
            for t in resultado.fired
        ],
        "observacao": (
            "Ocorrência com analisada=false ainda está na fila da IA. Os insights aparecem em "
            "lognix_listar_insights alguns segundos depois."
        ),
    }
