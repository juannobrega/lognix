"""Gerenciamento das chaves do MCP, para a aba Configurações > MCP. Ver ADR 017."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from lognix.auth.deps import CurrentUser, DbSession
from lognix.config import get_settings
from lognix.errors import ApiError
from lognix.mcp import keys as servico
from lognix.mcp.models import McpKey, McpScope
from lognix.mcp.server import CATALOGO
from lognix.settings import config_file
from lognix.settings import service as config

router = APIRouter(prefix="/settings/mcp", tags=["mcp"])


class EscopoOut(BaseModel):
    nome: str
    rotulo: str
    descricao: str
    risco: str


class FerramentaOut(BaseModel):
    nome: str
    escopo: str
    descricao: str


class ChaveOut(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    enabled: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    calls: int
    created_at: datetime
    #: Só na criação. Depois disso não existe mais em lugar nenhum legível.
    secret: str | None = None

    model_config = {"from_attributes": True}


class ChaveIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[McpScope] = Field(min_length=1)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class ChaveUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    scopes: list[McpScope] | None = None


class InfoOut(BaseModel):
    enabled: bool
    #: Existe chave que responde. Desligado e sem chave são motivos diferentes de não funcionar.
    has_keys: bool
    managed: bool
    url: str
    scopes: list[EscopoOut]
    tools: list[FerramentaOut]


ESCOPOS = [
    EscopoOut(
        nome="leitura",
        rotulo="Leitura",
        descricao="Hosts, projetos, logs, padrões, insights e ocorrências.",
        risco="Quem tiver a chave consegue ler os logs dos seus projetos.",
    ),
    EscopoOut(
        nome="analise",
        rotulo="Análise",
        descricao="Disparar uma análise por IA.",
        risco="Além de ler, gasta dinheiro com o provedor de IA configurado.",
    ),
    EscopoOut(
        nome="admin",
        rotulo="Administração",
        descricao="Consumo da IA e estado do sistema.",
        risco="Expõe custos e a topologia da instalação.",
    ),
]


class InfoIn(BaseModel):
    enabled: bool


async def _info(db: DbSession) -> InfoOut:
    from sqlalchemy import func, select

    base = get_settings().lognix_public_url.rstrip("/")
    chaves = (
        await db.execute(select(func.count()).select_from(McpKey).where(McpKey.enabled.is_(True)))
    ).scalar()
    return InfoOut(
        enabled=await config.get_bool(db, config.MCP_ENABLED),
        has_keys=bool(chaves),
        managed=config_file.is_managed(config.MCP_ENABLED),
        url=f"{base}/mcp",
        scopes=ESCOPOS,
        tools=[FerramentaOut(**f) for f in CATALOGO],
    )


@router.get("", response_model=InfoOut)
async def info(_: CurrentUser, db: DbSession) -> InfoOut:
    """O que o cliente precisa para se conectar, e o que cada escopo libera."""
    return await _info(db)


@router.put("", response_model=InfoOut)
async def ligar(body: InfoIn, _: CurrentUser, db: DbSession) -> InfoOut:
    """Interruptor geral. Desligado, `/mcp` responde 503 a todo mundo, com chave ou sem."""
    if config_file.is_managed(config.MCP_ENABLED):
        raise ApiError(
            409,
            "managed_by_file",
            "mcp.enabled está declarado no arquivo de configuração.",
            "Tire a chave do config.yaml para editar pela tela.",
        )
    await config.set_value(db, config.MCP_ENABLED, "true" if body.enabled else "false")
    await db.commit()
    return await _info(db)


@router.get("/keys", response_model=list[ChaveOut])
async def listar(_: CurrentUser, db: DbSession) -> list[ChaveOut]:
    from sqlalchemy import select

    linhas = (await db.execute(select(McpKey).order_by(McpKey.created_at.desc()))).scalars()
    return [ChaveOut.model_validate(k) for k in linhas]


@router.post("/keys", response_model=ChaveOut, status_code=status.HTTP_201_CREATED)
async def criar(body: ChaveIn, user: CurrentUser, db: DbSession) -> ChaveOut:
    """Cria a chave. O valor volta **uma vez**: depois disso só existe o hash."""
    from datetime import UTC, timedelta

    expira = (
        datetime.now(UTC) + timedelta(days=body.expires_in_days) if body.expires_in_days else None
    )
    registro, segredo = await servico.criar(
        db, nome=body.name, escopos=body.scopes, expira_em=expira, criada_por=user.id
    )
    saida = ChaveOut.model_validate(registro)
    saida.secret = segredo
    return saida


@router.put("/keys/{key_id}", response_model=ChaveOut)
async def atualizar(
    key_id: uuid.UUID, body: ChaveUpdate, _: CurrentUser, db: DbSession
) -> ChaveOut:
    registro = await db.get(McpKey, key_id)
    if registro is None:
        raise ApiError(404, "not_found", "Chave não encontrada.")
    if body.name is not None:
        registro.name = body.name.strip()
    if body.enabled is not None:
        registro.enabled = body.enabled
    if body.scopes is not None:
        registro.scopes = sorted({str(e) for e in body.scopes})
    await db.commit()
    await db.refresh(registro)
    return ChaveOut.model_validate(registro)


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revogar(key_id: uuid.UUID, _: CurrentUser, db: DbSession) -> None:
    registro = await db.get(McpKey, key_id)
    if registro is None:
        raise ApiError(404, "not_found", "Chave não encontrada.")
    await db.delete(registro)
    await db.commit()


class ChamadaOut(BaseModel):
    id: uuid.UUID
    key_name: str
    tool: str
    ok: bool
    error: str | None
    duration_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/calls", response_model=list[ChamadaOut])
async def chamadas(_: CurrentUser, db: DbSession, limit: int = 50) -> list[ChamadaOut]:
    """Quem chamou o quê. Sem isto não há como decidir qual chave revogar."""
    from sqlalchemy import select

    from lognix.mcp.models import McpCall

    linhas = (
        await db.execute(
            select(McpCall).order_by(McpCall.created_at.desc()).limit(max(1, min(limit, 200)))
        )
    ).scalars()
    return [ChamadaOut.model_validate(c) for c in linhas]
