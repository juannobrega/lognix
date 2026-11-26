"""Catálogo de providers configurados: criar, testar, ordenar, e a cadeia de fallback.

Credenciais ficam criptografadas em bloco, com o id do provider no AAD. Elas entram pela API e
nunca saem: o que volta é a lista de chaves preenchidas, não os valores.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.ai.models import (
    AiCall,
    AiCallStatus,
    AiModelConfig,
    AiProviderConfig,
    AiPurpose,
    CostSource,
    ProviderStatus,
)
from lognix.ai.provider import AiError, AiProvider, AiResult
from lognix.ai.providers import build_provider
from lognix.ai.providers.base import ProviderKind
from lognix.security.crypto import decrypt, encrypt

log = logging.getLogger(__name__)


def _aad(provider_id: uuid.UUID) -> str:
    return f"ai_provider:{provider_id}"


def store_credentials(provider: AiProviderConfig, values: dict[str, Any]) -> None:
    """Mescla as credenciais novas com as existentes. Valor vazio apaga a chave."""
    current = read_credentials(provider)
    for key, value in values.items():
        text = "" if value is None else str(value).strip()
        if text:
            current[key] = text
        else:
            current.pop(key, None)
    provider.credentials_enc = (
        encrypt(json.dumps(current), aad=_aad(provider.id)).encode() if current else None
    )
    provider.credential_keys = sorted(current)


def read_credentials(provider: AiProviderConfig) -> dict[str, Any]:
    if not provider.credentials_enc:
        return {}
    try:
        data = json.loads(decrypt(provider.credentials_enc.decode(), aad=_aad(provider.id)))
    except Exception:
        log.error(
            "não foi possível ler as credenciais do provider", extra={"provider": provider.name}
        )
        return {}
    return data if isinstance(data, dict) else {}


def open_provider(provider: AiProviderConfig) -> AiProvider:
    return build_provider(provider.kind, read_credentials(provider))


async def list_providers(db: AsyncSession) -> list[AiProviderConfig]:
    stmt = select(AiProviderConfig).order_by(AiProviderConfig.priority, AiProviderConfig.created_at)
    return list((await db.execute(stmt)).scalars())


async def usable_chain(db: AsyncSession) -> list[AiProviderConfig]:
    """Providers habilitados, com credencial e modelo padrão, na ordem de fallback."""
    return [
        p for p in await list_providers(db) if p.enabled and p.credentials_enc and p.default_model
    ]


async def next_priority(db: AsyncSession) -> int:
    highest = (await db.execute(select(func.max(AiProviderConfig.priority)))).scalar()
    return int(highest or 0) + 1


async def mark_checked(
    db: AsyncSession, provider: AiProviderConfig, *, ok: bool, error: str | None = None
) -> None:
    provider.last_status = ProviderStatus.ok if ok else ProviderStatus.error
    provider.last_error = (error or None) if not ok else None
    provider.last_checked_at = datetime.now(UTC)
    await db.commit()


@dataclass(frozen=True)
class ModelPrice:
    prompt_usd_per_mtok: Decimal | None
    completion_usd_per_mtok: Decimal | None

    def cost_for(self, input_tokens: int, output_tokens: int) -> Decimal | None:
        if self.prompt_usd_per_mtok is None and self.completion_usd_per_mtok is None:
            return None
        prompt = self.prompt_usd_per_mtok or Decimal(0)
        completion = self.completion_usd_per_mtok or Decimal(0)
        total = (Decimal(input_tokens) / 1_000_000) * prompt + (
            Decimal(output_tokens) / 1_000_000
        ) * completion
        return total.quantize(Decimal("0.000001"))


async def price_for(db: AsyncSession, provider_id: uuid.UUID, model_id: str) -> ModelPrice:
    stmt = select(AiModelConfig).where(
        AiModelConfig.provider_id == provider_id, AiModelConfig.model_id == model_id
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return ModelPrice(None, None)
    return ModelPrice(row.prompt_usd_per_mtok, row.completion_usd_per_mtok)


async def apply_price(
    db: AsyncSession, provider: AiProviderConfig, model_id: str, result: AiResult
) -> AiResult:
    """Completa o custo quando o provider não o informa, usando o preço cadastrado."""
    if result.cost_source == CostSource.provider and result.cost_usd > 0:
        return result
    price = await price_for(db, provider.id, model_id)
    cost = price.cost_for(result.input_tokens, result.output_tokens)
    if cost is None:
        return result
    result.cost_usd = cost
    result.cost_source = CostSource.estimated
    return result


async def sync_catalog(db: AsyncSession, provider: AiProviderConfig) -> list[AiModelConfig]:
    """Busca o catálogo do provider e guarda os modelos que ainda não estão cadastrados."""
    client = open_provider(provider)
    try:
        catalog = await client.models()
    finally:
        await client.aclose()
    existing = {m.model_id: m for m in provider.models}
    added: list[AiModelConfig] = []
    for info in catalog:
        row = existing.get(info.id)
        prompt = (
            Decimal(str(round(info.prompt_usd_per_mtok, 4))) if info.prompt_usd_per_mtok else None
        )
        completion = (
            Decimal(str(round(info.completion_usd_per_mtok, 4)))
            if info.completion_usd_per_mtok
            else None
        )
        if row is None:
            continue  # o catálogo é só para escolher; cadastrar é ato explícito
        # Atualiza preço e contexto de quem já está cadastrado.
        if prompt is not None:
            row.prompt_usd_per_mtok = prompt
        if completion is not None:
            row.completion_usd_per_mtok = completion
        if info.context_length:
            row.context_length = info.context_length
    await db.commit()
    return added


async def ensure_model(
    db: AsyncSession,
    provider: AiProviderConfig,
    model_id: str,
    *,
    label: str = "",
    context_length: int | None = None,
    prompt_price: Decimal | None = None,
    completion_price: Decimal | None = None,
) -> AiModelConfig:
    stmt = select(AiModelConfig).where(
        AiModelConfig.provider_id == provider.id, AiModelConfig.model_id == model_id
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = AiModelConfig(provider_id=provider.id, model_id=model_id)
        db.add(row)
    row.label = label or row.label or model_id
    if context_length is not None:
        row.context_length = context_length
    if prompt_price is not None:
        row.prompt_usd_per_mtok = prompt_price
    if completion_price is not None:
        row.completion_usd_per_mtok = completion_price
    await db.flush()
    return row


def _record_test(
    db: AsyncSession,
    provider: AiProviderConfig,
    model: str,
    *,
    result: AiResult | None = None,
    error: str | None = None,
) -> None:
    """Registra o teste em `ai_calls`.

    Um teste é uma chamada de verdade: sai pela rede e é cobrada. Não registrá-la abre um buraco
    exatamente onde o produto promete não ter nenhum — quem testa dez provedores gasta dez vezes
    e não vê nada em Consumo. O erro também entra, porque "o teste falhou e por quê" é a pergunta
    que se faz depois.
    """
    db.add(
        AiCall(
            provider_id=provider.id,
            provider=str(provider.kind),
            provider_name=provider.name,
            model=model,
            purpose=AiPurpose.test,
            input_tokens=result.input_tokens if result else 0,
            output_tokens=result.output_tokens if result else 0,
            cost_usd=result.cost_usd if result else Decimal(0),
            cost_source=result.cost_source if result else CostSource.unknown,
            latency_ms=result.latency_ms if result else 0,
            status=AiCallStatus.ok if result else AiCallStatus.error,
            error=error,
        )
    )


async def test_provider(
    db: AsyncSession, provider: AiProviderConfig, model: str | None = None
) -> tuple[bool, str | None, AiResult | None]:
    """Chamada mínima para validar credencial e modelo. Grava o resultado no provider."""
    target = model or provider.default_model
    if not target:
        # Nada saiu pela rede: não há chamada para registrar.
        await mark_checked(db, provider, ok=False, error="Nenhum modelo escolhido.")
        return False, "Escolha um modelo antes de testar.", None
    try:
        client = open_provider(provider)
    except AiError as exc:
        # Credencial incompleta: também não chegou a sair nada.
        await mark_checked(db, provider, ok=False, error=exc.message)
        return False, exc.message, None
    try:
        result = await client.test(target)  # type: ignore[attr-defined]
    except AiError as exc:
        _record_test(db, provider, target, error=exc.message)
        await mark_checked(db, provider, ok=False, error=exc.message)
        return False, exc.message, None
    finally:
        await client.aclose()
    result = await apply_price(db, provider, target, result)
    _record_test(db, provider, target, result=result)
    await mark_checked(db, provider, ok=True)
    return True, None, result


async def import_legacy_openrouter(db: AsyncSession) -> AiProviderConfig | None:
    """Move a chave única da 0.9.0 para a tabela de providers, uma vez só.

    Antes da 1.0.0 havia uma chave do OpenRouter e um modelo em `settings`. A cadeia de fallback
    não os lê. Em vez de pedir que o usuário reconfigure, na primeira subida nós criamos o provider
    equivalente e apagamos as configurações antigas, o que também impede o import de repetir.
    """
    from lognix.settings import service as settings_service

    api_key = await settings_service.get(db, settings_service.AI_API_KEY)
    model = (await settings_service.get(db, settings_service.AI_MODEL) or "").strip()
    if not api_key and not model:
        return None
    existing = (await db.execute(select(AiProviderConfig))).scalars().first()
    if api_key and existing is None:
        provider = AiProviderConfig(
            kind=ProviderKind.openrouter,
            name="OpenRouter",
            enabled=True,
            priority=1,
            default_model=model or None,
        )
        db.add(provider)
        await db.flush()
        store_credentials(provider, {"api_key": api_key})
        if model:
            await ensure_model(db, provider, model, label=model)
        log.info("chave do OpenRouter migrada para a cadeia de providers")
    else:
        # Sem chave antiga, ou já há providers cadastrados: o que sobrou em settings é lixo.
        provider = None
    await settings_service.set_value(db, settings_service.AI_API_KEY, None)
    await settings_service.set_value(db, settings_service.AI_MODEL, None)
    await db.commit()
    return provider
