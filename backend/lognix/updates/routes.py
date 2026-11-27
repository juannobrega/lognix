"""Rota da verificação de atualização. Ver ADR 018."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from lognix import __version__
from lognix.auth.deps import CurrentUser, DbSession
from lognix.errors import ApiError
from lognix.settings import config_file
from lognix.settings import service as config
from lognix.updates import service

router = APIRouter(prefix="/system/update", tags=["system"])

#: Onde quem lê a faixa vai ver o que mudou.
CHANGELOG = "https://juannobrega.github.io/lognix/CHANGELOG/"


class AtualizacaoOut(BaseModel):
    enabled: bool
    managed: bool
    current: str
    #: Nulo quando a verificação está desligada ou o registro não respondeu.
    available: str | None
    outdated: bool
    checked_at: datetime | None
    changelog_url: str
    #: Pronto para copiar. O compose segue `latest` por padrão, então não leva versão.
    command: str


class AtualizacaoIn(BaseModel):
    enabled: bool


async def _saida(db: DbSession) -> AtualizacaoOut:
    ligada = await config.get_bool(db, config.UPDATE_CHECK)
    resultado = await service.verificar() if ligada else None
    return AtualizacaoOut(
        enabled=ligada,
        managed=config_file.is_managed(config.UPDATE_CHECK),
        current=__version__,
        available=resultado.disponivel if resultado else None,
        outdated=bool(resultado and resultado.tem_novidade),
        checked_at=(datetime.fromtimestamp(resultado.verificado_em, tz=UTC) if resultado else None),
        changelog_url=CHANGELOG,
        command="docker compose pull && docker compose up -d",
    )


@router.get("", response_model=AtualizacaoOut)
async def estado(_: CurrentUser, db: DbSession) -> AtualizacaoOut:
    return await _saida(db)


@router.put("", response_model=AtualizacaoOut)
async def ligar(body: AtualizacaoIn, _: CurrentUser, db: DbSession) -> AtualizacaoOut:
    if config_file.is_managed(config.UPDATE_CHECK):
        raise ApiError(
            409,
            "managed_by_file",
            "updates.check_enabled está declarado no arquivo de configuração.",
            "Tire a chave do config.yaml para editar pela tela.",
        )
    await config.set_value(db, config.UPDATE_CHECK, "true" if body.enabled else "false")
    await db.commit()
    # Ligar agora significa querer a resposta agora, não dentro de seis horas.
    service.limpar_cache()
    return await _saida(db)
