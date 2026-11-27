"""Configuração dos canais de integração. Ver ADR 020."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from lognix.auth.deps import CurrentUser, DbSession
from lognix.errors import ApiError
from lognix.integrations import alerts
from lognix.integrations.smtp import PRESETS, EnvioError, enviar
from lognix.settings import config_file
from lognix.settings import service as config

router = APIRouter(prefix="/integrations", tags=["integrations"])

SEVERIDADES = ["critical", "high", "medium", "low", "info"]
SEGURANCAS = ["starttls", "tls", "none"]


class PresetOut(BaseModel):
    id: str
    label: str
    host: str
    port: int
    security: str
    hint: str
    username: str


class EmailOut(BaseModel):
    enabled: bool
    provider: str
    host: str
    port: int
    security: str
    username: str
    #: Nunca o valor. Só se existe uma senha guardada.
    has_password: bool
    sender: str
    recipients: str
    min_severity: str
    projects: str
    on_host_down: bool
    managed: list[str]
    presets: list[PresetOut]


class EmailIn(BaseModel):
    enabled: bool | None = None
    provider: str | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    security: str | None = None
    username: str | None = None
    #: Em branco mantém o que está guardado; é o mesmo contrato dos provedores de IA.
    password: str | None = None
    sender: str | None = None
    recipients: str | None = None
    min_severity: str | None = None
    projects: str | None = None
    on_host_down: bool | None = None


CHAVES = {
    "enabled": config.SMTP_ENABLED,
    "provider": config.SMTP_PROVIDER,
    "host": config.SMTP_HOST,
    "port": config.SMTP_PORT,
    "security": config.SMTP_SECURITY,
    "username": config.SMTP_USERNAME,
    "password": config.SMTP_PASSWORD,
    "sender": config.SMTP_FROM,
    "recipients": config.SMTP_TO,
    "min_severity": config.ALERTS_MIN_SEVERITY,
    "projects": config.ALERTS_PROJECTS,
    "on_host_down": config.ALERTS_ON_HOST_DOWN,
}


async def _saida(db: DbSession) -> EmailOut:
    return EmailOut(
        enabled=await config.get_bool(db, config.SMTP_ENABLED),
        provider=await config.get(db, config.SMTP_PROVIDER) or "",
        host=await config.get(db, config.SMTP_HOST) or "",
        port=await config.get_int(db, config.SMTP_PORT, 587),
        security=await config.get(db, config.SMTP_SECURITY) or "starttls",
        username=await config.get(db, config.SMTP_USERNAME) or "",
        has_password=await config.has_secret(db, config.SMTP_PASSWORD),
        sender=await config.get(db, config.SMTP_FROM) or "",
        recipients=await config.get(db, config.SMTP_TO) or "",
        min_severity=await config.get(db, config.ALERTS_MIN_SEVERITY) or "high",
        projects=await config.get(db, config.ALERTS_PROJECTS) or "",
        on_host_down=await config.get_bool(db, config.ALERTS_ON_HOST_DOWN),
        managed=sorted(c for c in CHAVES.values() if config_file.is_managed(c)),
        presets=[PresetOut(**p.__dict__) for p in PRESETS],
    )


@router.get("/email", response_model=EmailOut)
async def estado(_: CurrentUser, db: DbSession) -> EmailOut:
    return await _saida(db)


@router.put("/email", response_model=EmailOut)
async def salvar(body: EmailIn, _: CurrentUser, db: DbSession) -> EmailOut:
    if body.min_severity is not None and body.min_severity not in SEVERIDADES:
        raise ApiError(400, "bad_severity", f"Severidade deve ser uma de {SEVERIDADES}.")
    if body.security is not None and body.security not in SEGURANCAS:
        raise ApiError(400, "bad_security", f"Segurança deve ser uma de {SEGURANCAS}.")

    for campo, chave in CHAVES.items():
        valor = getattr(body, campo)
        if valor is None:
            continue
        # Senha em branco mantém a que está guardada: é o contrato dos provedores de IA, e
        # sem ele todo salvamento de outro campo apagaria a senha.
        if campo == "password" and valor == "":
            continue
        if config_file.is_managed(chave):
            raise ApiError(
                409,
                "managed_by_file",
                f"{chave} está declarado no arquivo de configuração.",
                "Tire a chave do config.yaml para editar pela tela.",
            )
        texto = "true" if valor is True else "false" if valor is False else str(valor)
        await config.set_value(db, chave, texto)
    await db.commit()
    return await _saida(db)


class TesteOut(BaseModel):
    ok: bool
    error: str | None


@router.post("/email/test", response_model=TesteOut)
async def testar(_: CurrentUser, db: DbSession) -> TesteOut:
    """Manda um e-mail de verdade. É o único jeito honesto de dizer que funciona."""
    try:
        await enviar(
            await alerts.conta(db),
            "[Lognix] Teste de envio",
            "Se esta mensagem chegou, o Lognix consegue avisar por e-mail.\n"
            "Os alertas de insight seguem a regra configurada na mesma tela.",
        )
    except EnvioError as exc:
        return TesteOut(ok=False, error=str(exc))
    return TesteOut(ok=True, error=None)
