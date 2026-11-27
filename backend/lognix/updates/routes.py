"""Rota da verificação de atualização. Ver ADR 018."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, status
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

log = logging.getLogger("lognix.updates")

#: Cada impedimento tem conserto diferente, então cada um tem frase própria.
MOTIVOS = {
    "socket_ausente": (
        "O socket do Docker não está montado no contêiner do Lognix, então ele não tem como "
        "trocar a própria imagem."
    ),
    "sem_permissao": (
        "O socket do Docker está montado, mas o processo do Lognix não tem permissão para usá-lo. "
        "Falta o group_add com o grupo docker do host."
    ),
    "container_desconhecido": (
        "O Docker respondeu, mas não soube dizer qual contêiner é o do Lognix."
    ),
    "docker_indisponivel": "O Docker desta máquina não respondeu.",
}


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

    # --- autoatualização, ADR 019 ---
    #: Interruptor próprio, independente da verificação.
    self_update_enabled: bool
    self_update_managed: bool
    #: O botão só aparece se houver caminho para a troca.
    can_self_update: bool
    #: Troca em curso: versao, fase e erro. A fase "falhou" é o que conta um pull que não deu.
    in_progress: dict[str, str | None] | None
    #: Por que não pode: socket_ausente, sem_permissao, container_desconhecido, docker_indisponivel.
    blocker: str | None
    last_attempt: TentativaOut | None


class AtualizacaoIn(BaseModel):
    enabled: bool | None = None
    self_update_enabled: bool | None = None


class AplicarIn(BaseModel):
    version: str


class TentativaOut(BaseModel):
    state: str
    exit_code: int | None
    finished_at: str | None
    log: str


async def _saida(db: DbSession) -> AtualizacaoOut:
    ligada = await config.get_bool(db, config.UPDATE_CHECK)
    resultado = await service.verificar() if ligada else None
    auto = await config.get_bool(db, config.SELF_UPDATE)
    quem = await service.capacidade() if auto else None
    tentativa = await service.ultima_tentativa() if auto else None
    return AtualizacaoOut(
        enabled=ligada,
        managed=config_file.is_managed(config.UPDATE_CHECK),
        current=__version__,
        available=resultado.disponivel if resultado else None,
        outdated=bool(resultado and resultado.tem_novidade),
        checked_at=(datetime.fromtimestamp(resultado.verificado_em, tz=UTC) if resultado else None),
        changelog_url=CHANGELOG,
        command="docker compose pull && docker compose up -d",
        self_update_enabled=auto,
        self_update_managed=config_file.is_managed(config.SELF_UPDATE),
        can_self_update=bool(quem and quem.pode),
        in_progress=(
            {"version": andamento.versao, "phase": andamento.fase, "error": andamento.erro}
            if (andamento := service.progresso())
            else None
        ),
        blocker=(quem.motivo if quem and not quem.pode else None),
        last_attempt=(
            TentativaOut(
                state=tentativa.estado,
                exit_code=tentativa.codigo,
                finished_at=tentativa.terminou_em,
                log=tentativa.registros,
            )
            if tentativa
            else None
        ),
    )


@router.get("", response_model=AtualizacaoOut)
async def estado(_: CurrentUser, db: DbSession) -> AtualizacaoOut:
    return await _saida(db)


@router.put("", response_model=AtualizacaoOut)
async def ligar(body: AtualizacaoIn, _: CurrentUser, db: DbSession) -> AtualizacaoOut:
    for chave, valor in (
        (config.UPDATE_CHECK, body.enabled),
        (config.SELF_UPDATE, body.self_update_enabled),
    ):
        if valor is None:
            continue
        if config_file.is_managed(chave):
            raise ApiError(
                409,
                "managed_by_file",
                f"{chave} está declarado no arquivo de configuração.",
                "Tire a chave do config.yaml para editar pela tela.",
            )
        await config.set_value(db, chave, "true" if valor else "false")
    await db.commit()
    # Ligar agora significa querer a resposta agora, não dentro de seis horas.
    service.limpar_cache()
    return await _saida(db)


@router.post("/apply", response_model=TentativaOut, status_code=status.HTTP_202_ACCEPTED)
async def aplicar(body: AplicarIn, user: CurrentUser, db: DbSession) -> TentativaOut:
    """Baixa a versão pedida e sobe o auxiliar que troca a imagem. Ver ADR 019.

    Devolve 202 e **cai**: o auxiliar para este contêiner alguns segundos depois. Quem chamou
    descobre o fim pela tela do Lognix novo, que lê os registros do auxiliar.
    """
    if not await config.get_bool(db, config.SELF_UPDATE):
        raise ApiError(
            409,
            "self_update_disabled",
            "A atualização pela interface está desligada.",
            "Ligue em Configurações > Sistema.",
        )
    try:
        versao = await service.alvo_valido(body.version)
    except ValueError as exc:
        raise ApiError(400, "invalid_version", str(exc)) from exc
    except Exception as exc:
        # Registro fora do alcance: sem isto a resposta seria um 500 opaco.
        raise ApiError(
            502,
            "registry_unreachable",
            "Não consegui conferir a versão no registro de imagens.",
            "Tente de novo quando a máquina tiver acesso ao ghcr.io.",
        ) from exc

    log.warning(
        "atualização para %s pedida por %s", versao, user.email, extra={"user_id": str(user.id)}
    )
    quem = await service.capacidade()
    if not quem.pode:
        raise ApiError(
            409, "no_docker_access", MOTIVOS.get(quem.motivo, "Não há acesso ao Docker.")
        )
    if (atual := service.progresso()) and atual.fase in {"baixando", "trocando"}:
        raise ApiError(
            409,
            "update_in_progress",
            f"Já existe uma atualização para {atual.versao} em andamento.",
        )
    await service.disparar(versao)
    return TentativaOut(state="running", exit_code=None, finished_at=None, log="")
