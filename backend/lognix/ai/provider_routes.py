"""Rotas de configuração de providers de IA: cadastrar, testar, ordenar, gerenciar modelos."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from lognix.ai import registry
from lognix.ai.models import AiModelConfig, AiProviderConfig, ProviderStatus
from lognix.ai.provider import AiError
from lognix.ai.providers import ProviderKind
from lognix.ai.providers.base import CREDENTIAL_FIELDS, HAS_CATALOG, PROVIDER_LABEL
from lognix.ai.service import get_runtime
from lognix.auth.deps import CurrentUser, DbSession
from lognix.errors import ApiError

router = APIRouter(prefix="/settings/ai/providers", tags=["ai-providers"])


class CredentialField(BaseModel):
    key: str
    label: str
    secret: bool
    required: bool
    placeholder: str = ""
    help: str = ""


class ProviderKindOut(BaseModel):
    kind: ProviderKind
    label: str
    has_catalog: bool
    fields: list[CredentialField]


class ModelOut(BaseModel):
    id: uuid.UUID
    model_id: str
    label: str
    enabled: bool
    context_length: int | None
    prompt_usd_per_mtok: Decimal | None
    completion_usd_per_mtok: Decimal | None

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class ProviderOut(BaseModel):
    id: uuid.UUID
    kind: ProviderKind
    label: str
    name: str
    enabled: bool
    priority: int
    default_model: str | None
    credential_keys: list[str]
    has_credentials: bool
    last_status: ProviderStatus
    last_error: str | None
    last_checked_at: datetime | None
    paused_until: datetime | None
    ready: bool
    models: list[ModelOut]

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class ProviderCreate(BaseModel):
    kind: ProviderKind
    name: str = Field(min_length=1, max_length=80)
    credentials: dict[str, str] = Field(default_factory=dict)
    default_model: str | None = Field(default=None, max_length=160)
    enabled: bool = False


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    credentials: dict[str, str] | None = None
    default_model: str | None = Field(default=None, max_length=160)
    enabled: bool | None = None


class ReorderIn(BaseModel):
    provider_ids: list[uuid.UUID]


class TestIn(BaseModel):
    model: str | None = Field(default=None, max_length=160)


class TestOut(BaseModel):
    ok: bool
    model: str | None = None
    latency_ms: int | None = None
    cost_usd: Decimal | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None


class CatalogModel(BaseModel):
    id: str
    name: str
    context_length: int | None = None
    prompt_usd_per_mtok: float | None = None
    completion_usd_per_mtok: float | None = None
    already_added: bool = False


class ModelIn(BaseModel):
    model_id: str = Field(min_length=1, max_length=160)
    label: str = Field(default="", max_length=160)
    context_length: int | None = Field(default=None, ge=1)
    prompt_usd_per_mtok: Decimal | None = Field(default=None, ge=0)
    completion_usd_per_mtok: Decimal | None = Field(default=None, ge=0)

    model_config = {"protected_namespaces": ()}


class ModelUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=160)
    enabled: bool | None = None
    context_length: int | None = Field(default=None, ge=1)
    prompt_usd_per_mtok: Decimal | None = Field(default=None, ge=0)
    completion_usd_per_mtok: Decimal | None = Field(default=None, ge=0)


def _out(p: AiProviderConfig) -> ProviderOut:
    kind = ProviderKind(p.kind)
    return ProviderOut(
        id=p.id,
        kind=kind,
        label=PROVIDER_LABEL[kind],
        name=p.name,
        enabled=p.enabled,
        priority=p.priority,
        default_model=p.default_model,
        credential_keys=list(p.credential_keys or []),
        has_credentials=p.credentials_enc is not None,
        last_status=p.last_status,
        last_error=p.last_error,
        last_checked_at=p.last_checked_at,
        paused_until=get_runtime().paused_until(p.id),
        ready=bool(p.enabled and p.credentials_enc and p.default_model),
        models=[ModelOut.model_validate(m) for m in sorted(p.models, key=lambda m: m.model_id)],
    )


async def _get(db: DbSession, provider_id: uuid.UUID) -> AiProviderConfig:
    p = await db.get(AiProviderConfig, provider_id)
    if p is None:
        raise ApiError(404, "not_found", "Provider não encontrado.")
    return p


@router.get("/kinds", response_model=list[ProviderKindOut])
async def kinds(_: CurrentUser) -> list[ProviderKindOut]:
    """Tipos disponíveis e os campos que cada um pede. A interface se monta a partir daqui."""
    return [
        ProviderKindOut(
            kind=k,
            label=PROVIDER_LABEL[k],
            has_catalog=HAS_CATALOG[k],
            fields=[CredentialField(**f) for f in CREDENTIAL_FIELDS[k]],
        )
        for k in ProviderKind
    ]


@router.get("", response_model=list[ProviderOut])
async def list_providers(_: CurrentUser, db: DbSession) -> list[ProviderOut]:
    return [_out(p) for p in await registry.list_providers(db)]


@router.post("", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(body: ProviderCreate, _: CurrentUser, db: DbSession) -> ProviderOut:
    provider = AiProviderConfig(
        id=uuid.uuid4(),
        kind=body.kind.value,
        name=body.name.strip(),
        default_model=(body.default_model or "").strip() or None,
        priority=await registry.next_priority(db),
    )
    db.add(provider)
    await db.flush()
    if body.credentials:
        registry.store_credentials(provider, body.credentials)
    if body.enabled:
        if not (provider.credentials_enc and provider.default_model):
            raise ApiError(
                400,
                "provider_not_ready",
                "Informe as credenciais e o modelo padrão antes de ativar.",
                "Preencha os campos e salve; depois ative.",
            )
        provider.enabled = True
    await db.commit()
    await db.refresh(provider)
    return _out(provider)


@router.put("/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: uuid.UUID, body: ProviderUpdate, _: CurrentUser, db: DbSession
) -> ProviderOut:
    provider = await _get(db, provider_id)
    if body.name is not None:
        provider.name = body.name.strip()
    if body.credentials is not None:
        registry.store_credentials(provider, body.credentials)
    if body.default_model is not None:
        provider.default_model = body.default_model.strip() or None
    if body.enabled is not None:
        if body.enabled and not (provider.credentials_enc and provider.default_model):
            raise ApiError(
                400,
                "provider_not_ready",
                "Informe as credenciais e o modelo padrão antes de ativar.",
                "Preencha os campos e salve; depois ative.",
            )
        provider.enabled = body.enabled
    provider.updated_at = datetime.now(tz=None).astimezone()
    await db.commit()
    await db.refresh(provider)
    return _out(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(provider_id: uuid.UUID, _: CurrentUser, db: DbSession) -> None:
    provider = await _get(db, provider_id)
    await db.delete(provider)
    await db.commit()


@router.post("/reorder", response_model=list[ProviderOut])
async def reorder(body: ReorderIn, _: CurrentUser, db: DbSession) -> list[ProviderOut]:
    """Define a ordem da cadeia de fallback. O primeiro da lista é o preferido."""
    providers = {p.id: p for p in await registry.list_providers(db)}
    unknown = [str(i) for i in body.provider_ids if i not in providers]
    if unknown:
        raise ApiError(400, "unknown_provider", f"Providers desconhecidos: {', '.join(unknown)}.")
    for position, provider_id in enumerate(body.provider_ids):
        providers[provider_id].priority = position
    await db.commit()
    return [_out(p) for p in await registry.list_providers(db)]


@router.post("/{provider_id}/test", response_model=TestOut)
async def test_provider(
    provider_id: uuid.UUID, body: TestIn, _: CurrentUser, db: DbSession
) -> TestOut:
    provider = await _get(db, provider_id)
    ok, error, result = await registry.test_provider(db, provider, body.model)
    if not ok or result is None:
        return TestOut(ok=False, error=error)
    return TestOut(
        ok=True,
        model=result.model,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


@router.get("/{provider_id}/catalog", response_model=list[CatalogModel])
async def catalog(
    provider_id: uuid.UUID,
    _: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[CatalogModel]:
    """Modelos que o provider oferece. Cadastrar é ato explícito, feito em seguida."""
    provider = await _get(db, provider_id)
    if not provider.credentials_enc:
        raise ApiError(
            400, "missing_credentials", "Salve as credenciais para listar os modelos disponíveis."
        )
    try:
        client = registry.open_provider(provider)
    except AiError as exc:
        raise ApiError(400, "provider_error", exc.message) from exc
    try:
        models = await client.models()
    except AiError as exc:
        raise ApiError(502, "provider_error", exc.message) from exc
    finally:
        await client.aclose()
    added = {m.model_id for m in provider.models}
    needle = (q or "").lower()
    return [
        CatalogModel(
            id=m.id,
            name=m.name,
            context_length=m.context_length,
            prompt_usd_per_mtok=m.prompt_usd_per_mtok,
            completion_usd_per_mtok=m.completion_usd_per_mtok,
            already_added=m.id in added,
        )
        for m in models
        if not needle or needle in m.id.lower() or needle in m.name.lower()
    ][:300]


@router.post(
    "/{provider_id}/models", response_model=ProviderOut, status_code=status.HTTP_201_CREATED
)
async def add_model(
    provider_id: uuid.UUID, body: ModelIn, _: CurrentUser, db: DbSession
) -> ProviderOut:
    provider = await _get(db, provider_id)
    await registry.ensure_model(
        db,
        provider,
        body.model_id.strip(),
        label=body.label.strip(),
        context_length=body.context_length,
        prompt_price=body.prompt_usd_per_mtok,
        completion_price=body.completion_usd_per_mtok,
    )
    if provider.default_model is None:
        provider.default_model = body.model_id.strip()
    await db.commit()
    await db.refresh(provider)
    return _out(provider)


@router.put("/{provider_id}/models/{model_id}", response_model=ProviderOut)
async def update_model(
    provider_id: uuid.UUID,
    model_id: uuid.UUID,
    body: ModelUpdate,
    _: CurrentUser,
    db: DbSession,
) -> ProviderOut:
    provider = await _get(db, provider_id)
    row = await db.get(AiModelConfig, model_id)
    if row is None or row.provider_id != provider.id:
        raise ApiError(404, "not_found", "Modelo não encontrado neste provider.")
    if body.label is not None:
        row.label = body.label.strip() or row.model_id
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.context_length is not None:
        row.context_length = body.context_length
    if body.prompt_usd_per_mtok is not None:
        row.prompt_usd_per_mtok = body.prompt_usd_per_mtok
    if body.completion_usd_per_mtok is not None:
        row.completion_usd_per_mtok = body.completion_usd_per_mtok
    await db.commit()
    await db.refresh(provider)
    return _out(provider)


@router.delete("/{provider_id}/models/{model_id}", response_model=ProviderOut)
async def delete_model(
    provider_id: uuid.UUID, model_id: uuid.UUID, _: CurrentUser, db: DbSession
) -> ProviderOut:
    provider = await _get(db, provider_id)
    row = await db.get(AiModelConfig, model_id)
    if row is None or row.provider_id != provider.id:
        raise ApiError(404, "not_found", "Modelo não encontrado neste provider.")
    if provider.default_model == row.model_id:
        remaining = [m for m in provider.models if m.id != row.id]
        provider.default_model = remaining[0].model_id if remaining else None
        if provider.default_model is None:
            provider.enabled = False
    await db.delete(row)
    await db.commit()
    await db.refresh(provider)
    return _out(provider)


@router.post("/{provider_id}/catalog/sync", response_model=ProviderOut)
async def sync_catalog(provider_id: uuid.UUID, _: CurrentUser, db: DbSession) -> ProviderOut:
    """Atualiza preço e janela de contexto dos modelos já cadastrados, a partir do catálogo."""
    provider = await _get(db, provider_id)
    try:
        await registry.sync_catalog(db, provider)
    except AiError as exc:
        raise ApiError(502, "provider_error", exc.message) from exc
    await db.refresh(provider)
    return _out(provider)
