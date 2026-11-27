"""Envio de e-mail por SMTP. Ver ADR 020.

SMTP, e não a API HTTP de um provedor: é um protocolo só que atende todos eles e o relay
interno da empresa — que é o caso comum de quem instala software auto-hospedado e não quer o
alerta saindo da rede.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr

log = logging.getLogger("lognix.integrations.smtp")

TIMEOUT = 20.0


@dataclass(frozen=True)
class Preset:
    """Host, porta e segurança de um provedor conhecido.

    Preenche, não trava: Amazon SES muda de host por região, e relay interno não tem preset.
    Errar esses três é a causa número um de "não envia", e a mensagem do SMTP não ajuda —
    `authentication failed` cobre desde senha errada até porta errada.
    """

    id: str
    label: str
    host: str
    port: int
    security: str
    #: O que a pessoa precisa saber antes de tentar, e que o provedor esconde na documentação.
    hint: str = ""
    username: str = ""


PRESETS: list[Preset] = [
    Preset(
        "gmail",
        "Gmail / Google Workspace",
        "smtp.gmail.com",
        587,
        "starttls",
        hint="Exige uma senha de app, não a senha da conta. Conta com 2FA ligado.",
    ),
    Preset("microsoft365", "Microsoft 365 / Outlook", "smtp.office365.com", 587, "starttls"),
    Preset(
        "ses",
        "Amazon SES",
        "email-smtp.us-east-1.amazonaws.com",
        587,
        "starttls",
        hint="Troque a região no host. A credencial SMTP do SES não é a sua chave da AWS.",
    ),
    Preset(
        "sendgrid",
        "SendGrid",
        "smtp.sendgrid.net",
        587,
        "starttls",
        hint="O usuário é literalmente 'apikey'; a senha é a chave.",
        username="apikey",
    ),
    Preset("mailgun", "Mailgun", "smtp.mailgun.org", 587, "starttls"),
    Preset(
        "postmark",
        "Postmark",
        "smtp.postmarkapp.com",
        587,
        "starttls",
        hint="Usuário e senha são o mesmo token do servidor.",
    ),
    Preset("resend", "Resend", "smtp.resend.com", 587, "starttls", username="resend"),
    Preset("brevo", "Brevo", "smtp-relay.brevo.com", 587, "starttls"),
    Preset("zoho", "Zoho Mail", "smtp.zoho.com", 587, "starttls"),
    Preset(
        "custom",
        "Servidor próprio",
        "",
        25,
        "none",
        hint="Relay interno, para quem não quer o alerta saindo da rede.",
    ),
]

POR_ID = {p.id: p for p in PRESETS}


@dataclass
class Conta:
    host: str
    port: int
    security: str
    username: str = ""
    password: str = ""
    remetente: str = ""
    nome: str = "Lognix"
    destinatarios: list[str] = field(default_factory=list)

    def valida(self) -> str | None:
        """Motivo de não dar para enviar, ou None. Separado do envio para a tela poder dizer
        o que falta sem abrir conexão nenhuma."""
        if not self.host:
            return "Falta o servidor SMTP."
        if not self.remetente:
            return "Falta o endereço remetente."
        if not self.destinatarios:
            return "Falta pelo menos um destinatário."
        return None


class EnvioError(Exception):
    """Falha ao enviar, já traduzida para alguém que não conhece SMTP."""


def _mensagem(conta: Conta, assunto: str, corpo: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = formataddr((conta.nome, conta.remetente))
    msg["To"] = ", ".join(conta.destinatarios)
    msg.set_content(corpo)
    return msg


def _entregar(conta: Conta, msg: EmailMessage) -> None:
    """Bloqueante, chamado numa thread. `smtplib` em vez de dependência nova: enviar é raro."""
    contexto = ssl.create_default_context()
    try:
        if conta.security == "tls":
            with smtplib.SMTP_SSL(
                conta.host, conta.port, timeout=TIMEOUT, context=contexto
            ) as servidor:
                if conta.username:
                    servidor.login(conta.username, conta.password)
                servidor.send_message(msg)
            return
        with smtplib.SMTP(conta.host, conta.port, timeout=TIMEOUT) as servidor:
            servidor.ehlo()
            if conta.security == "starttls":
                servidor.starttls(context=contexto)
                servidor.ehlo()
            if conta.username:
                servidor.login(conta.username, conta.password)
            servidor.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        # A mensagem do servidor cobre senha errada, porta errada e conta sem permissão de
        # envio. Repetir o texto cru é mais útil do que escolher um culpado.
        raise EnvioError(f"O servidor recusou as credenciais: {exc.smtp_error!r}") from exc
    except smtplib.SMTPNotSupportedError as exc:
        raise EnvioError(f"O servidor não aceita esse modo de segurança: {exc}") from exc
    except (OSError, smtplib.SMTPException) as exc:
        raise EnvioError(f"Não consegui falar com {conta.host}:{conta.port}: {exc}") from exc


async def enviar(conta: Conta, assunto: str, corpo: str) -> None:
    """Envia, ou levanta `EnvioError` com um motivo legível."""
    problema = conta.valida()
    if problema:
        raise EnvioError(problema)
    await asyncio.to_thread(_entregar, conta, _mensagem(conta, assunto, corpo))
    log.info("e-mail enviado", extra={"destinatarios": len(conta.destinatarios)})
