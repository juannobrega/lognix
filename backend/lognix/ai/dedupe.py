"""Deduplicação de insights. Ver ADR 016.

Um container em erro contínuo dispara um trigger a cada ciclo. Sem isto, cada um vira uma chamada
de IA e um insight novo: 2.880 por dia, de um container só. O custo é o argumento mais fácil, mas
não é o principal — mil cópias do mesmo diagnóstico enterram os outros problemas, e aí a tela que
existe para dizer o que está acontecendo passa a dizer menos.

A economia mora em **não fazer a chamada**. Encolher o contexto economiza porcentagem; não chamar
economiza a chamada inteira.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.ai.models import Insight, InsightStatus
from lognix.analysis.models import TriggerFired
from lognix.events.models import DockerEvent, DockerEventType

log = logging.getLogger(__name__)

#: Passado este tempo sem reaparecer, o problema conta como novo e merece análise nova: o
#: contexto mudou, pode ter sido corrigido e voltado, e a causa pode ser outra.
JANELA_PADRAO = timedelta(hours=6)

_NUMEROS = re.compile(r"\d+")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_HEX = re.compile(r"\b[0-9a-f]{12,}\b", re.I)


def chave(trigger: TriggerFired, amostras: list[str]) -> str:
    """Assinatura do problema, não do texto.

    "falhou para o usuário 12" e "falhou para o usuário 99" são o mesmo problema, então números,
    uuids e hashes saem antes de assinar. O tipo do trigger entra porque um OOM e um erro de
    aplicação no mesmo container são coisas diferentes mesmo com linhas parecidas.
    """
    corpo = "\n".join(sorted(amostras[:5]))
    for padrao in (_UUID, _HEX, _NUMEROS):
        corpo = padrao.sub("<n>", corpo)
    digest = hashlib.sha256(corpo.encode("utf-8", "replace")).hexdigest()[:40]
    return f"{trigger.type.value}:{digest}"


async def insight_ativo(
    db: AsyncSession,
    *,
    container_id: uuid.UUID,
    dedupe_key: str,
    janela: timedelta = JANELA_PADRAO,
    ate: datetime | None = None,
) -> Insight | None:
    """O insight que já cobre este problema, se houver um recente e ainda não visto.

    Três condições, e cada uma é uma decisão do ADR 016: mesma chave, ainda `new` — marcar como
    visto reabre a contagem, porque ocorrência depois de tratada é notícia —, e dentro da janela.
    """
    agora = ate or datetime.now(UTC)
    stmt = (
        select(Insight)
        .where(
            Insight.container_id == container_id,
            Insight.dedupe_key == dedupe_key,
            Insight.status == InsightStatus.new,
            Insight.last_seen_at >= agora - janela,
        )
        .order_by(Insight.last_seen_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def houve_redeploy(db: AsyncSession, *, container_id: uuid.UUID, depois_de: datetime) -> bool:
    """Redeploy quebra a deduplicação: a imagem mudou, então o mesmo erro é outro erro.

    E é justamente o momento em que o diagnóstico importa mais — "voltou a falhar depois do
    deploy" é a pergunta que alguém está fazendo nesse instante.
    """
    stmt = select(DockerEvent.id).where(
        DockerEvent.container_id == container_id,
        DockerEvent.type == DockerEventType.redeploy,
        DockerEvent.occurred_at > depois_de,
    )
    return (await db.execute(stmt.limit(1))).first() is not None


def registrar_ocorrencia(insight: Insight, trigger: TriggerFired) -> Insight:
    """Soma uma ocorrência ao insight existente, sem gastar um token."""
    insight.occurrences = (insight.occurrences or 1) + 1
    insight.last_seen_at = trigger.window_end or datetime.now(UTC)
    return insight
