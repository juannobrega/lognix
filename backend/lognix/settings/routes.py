"""Rotas de configuração. Segredos entram, mas nunca saem."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from lognix.auth.deps import CurrentUser, DbSession
from lognix.errors import ApiError
from lognix.settings import service

router = APIRouter(prefix="/settings", tags=["settings"])


class AiSettingsOut(BaseModel):
    enabled: bool  # interruptor
    configured: bool  # chave e modelo presentes: pode ser ligada
    active: bool  # configured e enabled: a IA roda
    has_api_key: bool
    model: str | None
    max_input_tokens: int
    max_output_tokens: int
    concurrency: int
    language: str
    provider: str = "openrouter"


class AiSettingsIn(BaseModel):
    enabled: bool | None = None
    api_key: str | None = Field(default=None, max_length=400)
    model: str | None = Field(default=None, max_length=200)
    max_input_tokens: int | None = Field(default=None, ge=1000, le=200_000)
    max_output_tokens: int | None = Field(default=None, ge=200, le=32_000)
    concurrency: int | None = Field(default=None, ge=1, le=20)


async def _ai_out(db: DbSession) -> AiSettingsOut:
    return AiSettingsOut(
        enabled=await service.get_bool(db, service.AI_ENABLED),
        configured=await service.ai_has_credentials(db),
        active=await service.ai_is_active(db),
        has_api_key=await service.has_secret(db, service.AI_API_KEY),
        model=await service.get(db, service.AI_MODEL),
        max_input_tokens=await service.get_int(db, service.AI_MAX_INPUT_TOKENS, 12000),
        max_output_tokens=await service.get_int(db, service.AI_MAX_OUTPUT_TOKENS, 1500),
        concurrency=await service.get_int(db, service.AI_CONCURRENCY, 3),
        language=await service.get(db, service.AI_LANGUAGE) or "pt-BR",
    )


@router.get("/ai", response_model=AiSettingsOut)
async def get_ai(_: CurrentUser, db: DbSession) -> AiSettingsOut:
    return await _ai_out(db)


@router.put("/ai", response_model=AiSettingsOut)
async def put_ai(body: AiSettingsIn, _: CurrentUser, db: DbSession) -> AiSettingsOut:
    if body.api_key is not None:
        # Campo vazio apaga a chave; qualquer outro valor substitui.
        await service.set_value(db, service.AI_API_KEY, body.api_key.strip() or None)
    if body.model is not None:
        await service.set_value(db, service.AI_MODEL, body.model.strip() or None)
    for key, value in (
        (service.AI_MAX_INPUT_TOKENS, body.max_input_tokens),
        (service.AI_MAX_OUTPUT_TOKENS, body.max_output_tokens),
        (service.AI_CONCURRENCY, body.concurrency),
    ):
        if value is not None:
            await service.set_value(db, key, str(value))
    if body.enabled is not None:
        if body.enabled and not await service.ai_has_credentials(db):
            raise ApiError(
                400,
                "ai_not_configured",
                "Informe a chave de API e o modelo antes de ativar a IA.",
                "Preencha os dois campos acima e salve.",
            )
        await service.set_value(db, service.AI_ENABLED, "true" if body.enabled else "false")
    await db.commit()
    return await _ai_out(db)
