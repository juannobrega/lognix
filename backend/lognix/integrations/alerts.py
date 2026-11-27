"""Quem vira e-mail, e com que texto. Ver ADR 020."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lognix.config import get_settings
from lognix.integrations.smtp import Conta, EnvioError, enviar
from lognix.settings import service as config

log = logging.getLogger("lognix.integrations.alerts")

#: Da mais grave para a mais branda. A regra guarda a mínima, e tudo acima dela passa.
ORDEM = ["critical", "high", "medium", "low", "info"]


def passa(severidade: str, minima: str) -> bool:
    try:
        return ORDEM.index(severidade) <= ORDEM.index(minima)
    except ValueError:
        # Severidade que não conhecemos não silencia o alerta: errar para mais é o lado certo.
        return True


async def conta(db: AsyncSession) -> Conta:
    destinos = (await config.get(db, config.SMTP_TO) or "").replace(";", ",")
    return Conta(
        host=await config.get(db, config.SMTP_HOST) or "",
        port=await config.get_int(db, config.SMTP_PORT, 587),
        security=await config.get(db, config.SMTP_SECURITY) or "starttls",
        username=await config.get(db, config.SMTP_USERNAME) or "",
        password=await config.get(db, config.SMTP_PASSWORD) or "",
        remetente=await config.get(db, config.SMTP_FROM) or "",
        destinatarios=[d.strip() for d in destinos.split(",") if d.strip()],
    )


async def _habilitado(db: AsyncSession) -> bool:
    return await config.get_bool(db, config.SMTP_ENABLED)


def _link(caminho: str) -> str:
    return f"{get_settings().lognix_public_url.rstrip('/')}{caminho}"


def texto_do_insight(insight: Any, projeto: str, host: str) -> tuple[str, str]:
    """Assunto e corpo. Sem linha de log de propósito — ver ADR 020.

    Caixa de e-mail é cópia que escapa do controle de acesso e fica para sempre; quem quer a
    evidência abre o Lognix, onde se sabe quem entrou.
    """
    severidade = str(insight.severity)
    assunto = f"[Lognix · {severidade}] {projeto}: {insight.title}"
    corpo = "\n".join(
        [
            insight.summary or "",
            "",
            f"Host: {host}",
            f"Projeto: {projeto}",
            f"Severidade: {severidade}",
            f"Confiança: {float(insight.confidence):.0%}",
            "",
            f"Causa provável: {insight.probable_cause}",
            f"Ação sugerida: {insight.suggested_action}",
            "",
            f"As evidências e o contexto enviado estão em {_link(f'/insights/{insight.id}')}",
        ]
    )
    return assunto, corpo


async def avisar_do_insight(db: AsyncSession, insight: Any, projeto: str, host: str) -> None:
    """Manda o alerta se a regra deixar. Nunca levanta: o insight já existe, e e-mail é entrega.

    Só é chamada quando o insight **nasce**. Recorrência atualiza a contagem do que já existe e
    não manda nada: um erro persistente viraria uma mensagem por ciclo, e o filtro de quem
    recebe aprenderia a jogar o Lognix no lixo.
    """
    try:
        if not await _habilitado(db):
            return
        minima = await config.get(db, config.ALERTS_MIN_SEVERITY) or "high"
        if not passa(str(insight.severity), minima):
            return
        projetos = [
            p.strip() for p in (await config.get(db, config.ALERTS_PROJECTS) or "").split(",")
        ]
        projetos = [p for p in projetos if p]
        if projetos and projeto not in projetos:
            return
        assunto, corpo = texto_do_insight(insight, projeto, host)
        await enviar(await conta(db), assunto, corpo)
    except EnvioError as exc:
        await _registrar_falha(db, str(exc))
    except Exception:
        log.exception("falha inesperada ao avisar do insight")


async def avisar_host_caiu(db: AsyncSession, host: str, motivo: str | None) -> None:
    try:
        if not await _habilitado(db) or not await config.get_bool(db, config.ALERTS_ON_HOST_DOWN):
            return
        corpo = "\n".join(
            [
                f"O Lognix perdeu a conexão com o host {host}.",
                f"Motivo: {motivo or 'não informado'}",
                "",
                "Enquanto isso, os containers daquele host não são coletados nem analisados.",
                "",
                _link("/hosts"),
            ]
        )
        await enviar(await conta(db), f"[Lognix] Host {host} desconectado", corpo)
    except EnvioError as exc:
        await _registrar_falha(db, str(exc))
    except Exception:
        log.exception("falha inesperada ao avisar que o host caiu")


async def _registrar_falha(db: AsyncSession, motivo: str) -> None:
    """Falha de entrega vira log e notificação na tela, nunca exceção que sobe para o ciclo."""
    from lognix.notifications.models import NotificationType
    from lognix.notifications.service import notify

    log.warning("não consegui enviar o alerta por e-mail: %s", motivo)
    try:
        await notify(
            db,
            NotificationType.email_failed,
            "Não consegui enviar o alerta por e-mail",
            payload={"error": motivo},
        )
        await db.commit()
    except Exception:
        log.exception("nem a notificação de falha de e-mail foi gravada")
