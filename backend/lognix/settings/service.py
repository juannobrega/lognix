"""Leitura e escrita de configurações. Segredos nunca saem em claro pela API."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.security.crypto import decrypt, encrypt
from lognix.settings.models import Setting

# Chaves conhecidas. Ver Planning > Modelo de Dados.
AI_API_KEY = "ai.openrouter.api_key"
AI_MODEL = "ai.openrouter.model"
AI_ENABLED = "ai.enabled"
AI_MAX_INPUT_TOKENS = "ai.max_input_tokens"
AI_MAX_OUTPUT_TOKENS = "ai.max_output_tokens"
AI_CONCURRENCY = "ai.concurrency"
AI_LANGUAGE = "ai.language"
MCP_ENABLED = "mcp.enabled"
UPDATE_CHECK = "updates.check_enabled"

SECRET_KEYS = frozenset({AI_API_KEY, "github.app.private_key"})

DEFAULTS: dict[str, str] = {
    AI_ENABLED: "false",
    # Desligado por padrão, como a IA: o endereço MCP serve logs, e nada que serve log
    # deveria passar a responder porque alguém atualizou a versão.
    MCP_ENABLED: "false",
    # Desligada: verificar atualização é chamada para fora, e a documentação promete não fazer
    # nenhuma sem que a pessoa peça. Ver ADR 018.
    UPDATE_CHECK: "false",
    AI_MAX_INPUT_TOKENS: "12000",
    AI_MAX_OUTPUT_TOKENS: "1500",
    AI_CONCURRENCY: "3",
    AI_LANGUAGE: "pt-BR",
}


def _aad(key: str) -> str:
    return f"setting:{key}"


async def get(db: AsyncSession, key: str) -> str | None:
    row = await db.get(Setting, key)
    if row is None:
        return DEFAULTS.get(key)
    if row.is_secret:
        return decrypt(row.value_enc.decode(), aad=_aad(key)) if row.value_enc else None
    return row.value if row.value is not None else DEFAULTS.get(key)


async def get_bool(db: AsyncSession, key: str) -> bool:
    return (await get(db, key) or "").strip().lower() in {"1", "true", "yes", "on"}


async def get_int(db: AsyncSession, key: str, fallback: int) -> int:
    try:
        return int(await get(db, key) or fallback)
    except (TypeError, ValueError):
        return fallback


async def set_value(db: AsyncSession, key: str, value: str | None) -> None:
    secret = key in SECRET_KEYS
    row = await db.get(Setting, key)
    if row is None:
        row = Setting(key=key, is_secret=secret)
        db.add(row)
    row.is_secret = secret
    if value is None:
        row.value = row.value_enc = None
    elif secret:
        row.value, row.value_enc = None, encrypt(value, aad=_aad(key)).encode()
    else:
        row.value, row.value_enc = value, None


async def has_secret(db: AsyncSession, key: str) -> bool:
    row = await db.get(Setting, key)
    return row is not None and row.value_enc is not None


async def ai_has_credentials(db: AsyncSession) -> bool:
    """Existe ao menos um provider com credencial e modelo. Diz se a IA *pode* ser ligada."""
    # Import local: o registry depende deste módulo para ler as configurações de IA.
    from lognix.ai.registry import usable_chain

    return bool(await usable_chain(db))


async def ai_is_active(db: AsyncSession) -> bool:
    """Credenciais presentes **e** interruptor ligado. É o que decide se a IA roda."""
    return await ai_has_credentials(db) and await get_bool(db, AI_ENABLED)


async def all_public(db: AsyncSession) -> dict[str, str | None]:
    """Todas as configurações, com segredos mascarados."""
    rows = {r.key: r for r in (await db.execute(select(Setting))).scalars()}
    out: dict[str, str | None] = dict(DEFAULTS)
    for key, row in rows.items():
        out[key] = "********" if row.is_secret and row.value_enc else row.value
    return out
