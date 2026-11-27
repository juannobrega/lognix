"""Descobre se existe versão nova publicada. Ver ADR 018.

Desligada por padrão: verificar atualização é uma chamada para fora, e a documentação do produto
promete não fazer nenhuma sem que a pessoa peça.

A fonte é a lista de tags do GHCR, e não a API de releases do GitHub, porque o que interessa é a
versão que dá para **baixar**. As duas já divergiram aqui: a v1.1.0 teve tag e release sem imagem
publicada, porque o build foi cancelado. Anunciar versão cujo `docker pull` falha é pior que não
anunciar nada.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass

import httpx

from lognix import __version__

log = logging.getLogger("lognix.updates")

REPOSITORIO = "juannobrega/lognix"
REGISTRO = "https://ghcr.io"
#: Só `X.Y.Z`. A lista do registro traz também `latest`, `1`, `1.3` e `buildcache`.
VERSAO = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
CACHE_SEGUNDOS = 6 * 3600
TIMEOUT = 10.0


def tupla(versao: str) -> tuple[int, int, int] | None:
    """`1.10.0` precisa sair maior que `1.9.0`, o que comparação de texto erra."""
    achado = VERSAO.match(versao.strip().lstrip("v"))
    return (int(achado[1]), int(achado[2]), int(achado[3])) if achado else None


@dataclass(frozen=True)
class Resultado:
    #: Versão rodando agora.
    atual: str
    #: Maior versão publicada, ou None quando a consulta não respondeu.
    disponivel: str | None
    #: Momento da consulta, para a tela dizer de quando é a informação.
    verificado_em: float

    @property
    def tem_novidade(self) -> bool:
        aqui, lá = tupla(self.atual), tupla(self.disponivel or "")
        return bool(aqui and lá and lá > aqui)


_cache: Resultado | None = None


def limpar_cache() -> None:
    """Para os testes, e para quando alguém liga a verificação e quer resposta na hora."""
    global _cache
    _cache = None


async def _tags(cliente: httpx.AsyncClient) -> list[str]:
    """Lista anônima: o GHCR dá um token de pull para repositório público."""
    resposta = await cliente.get(
        f"{REGISTRO}/token",
        params={"scope": f"repository:{REPOSITORIO}:pull", "service": "ghcr.io"},
        timeout=TIMEOUT,
    )
    resposta.raise_for_status()
    token = resposta.json().get("token")
    if not token:
        raise httpx.HTTPError("o registro não devolveu token de leitura")
    resposta = await cliente.get(
        f"{REGISTRO}/v2/{REPOSITORIO}/tags/list",
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    resposta.raise_for_status()
    return [str(t) for t in resposta.json().get("tags") or []]


async def verificar(
    *, transport: httpx.AsyncBaseTransport | None = None, agora: float | None = None
) -> Resultado:
    """Maior versão publicada, com cache de 6 horas.

    Falha de rede não é erro para quem usa: instalação em rede fechada é caso normal, e o
    resultado "não sei" é o que a tela precisa para não mostrar nada. O motivo fica no log.
    """
    global _cache
    momento = agora if agora is not None else time.time()
    if _cache is not None and momento - _cache.verificado_em < CACHE_SEGUNDOS:
        return _cache

    disponivel: str | None = None
    try:
        async with httpx.AsyncClient(transport=transport) as cliente:
            publicadas = [t for t in await _tags(cliente) if tupla(t)]
        if publicadas:
            disponivel = max(publicadas, key=lambda t: tupla(t) or (0, 0, 0))
    except Exception as exc:
        # Nem `exception`: sem internet isso encheria o log a cada 6 horas com algo esperado.
        log.info("não foi possível consultar o registro: %s", exc)

    _cache = Resultado(atual=__version__, disponivel=disponivel, verificado_em=momento)
    return _cache


# --- autoatualização ----------------------------------------------------------------------
#
# Ver ADR 019. Nada aqui roda sem duas chaves: o socket do Docker montado e alcançável, e a
# configuração ligada. A referência da imagem nunca vem do pedido — ver `alvo_valido`.

IMAGEM = f"ghcr.io/{REPOSITORIO}"


@dataclass(frozen=True)
class Capacidade:
    """Por que o botão aparece, ou por que não aparece."""

    pode: bool
    motivo: str
    #: Contêiner do Lognix, quando o Docker local soube dizer qual é.
    container: str | None = None
    nome: str | None = None


async def capacidade(socket: str | None = None) -> Capacidade:
    """Descobre se existe caminho para a troca, e devolve o motivo quando não existe.

    Os estados são distintos de propósito: socket ausente é decisão de quem instalou, e socket
    presente sem permissão é o processo fora do grupo `docker` — conserto diferente, mensagem
    diferente.
    """
    from pathlib import Path

    from lognix.updates.docker import SOCKET, DockerError, SemPermissaoError, abrir

    caminho = socket or SOCKET
    try:
        if not Path(caminho).is_socket():
            return Capacidade(False, "socket_ausente")
    except OSError:
        return Capacidade(False, "socket_ausente")

    docker = abrir(caminho)
    try:
        await docker.ping()
        # O hostname de um contêiner é o id curto dele, salvo quando alguém passou --hostname.
        import socket as rede

        eu = await docker.inspecionar(rede.gethostname())
        identificador = str(eu.get("Id") or "")
        nome = str(eu.get("Name") or "").lstrip("/")
        if not identificador or not nome:
            return Capacidade(False, "container_desconhecido")
        return Capacidade(True, "ok", container=identificador, nome=nome)
    except SemPermissaoError:
        return Capacidade(False, "sem_permissao")
    except DockerError as exc:
        if exc.status == 404:
            return Capacidade(False, "container_desconhecido")
        log.info("Docker local indisponível para autoatualização: %s", exc)
        return Capacidade(False, "docker_indisponivel")
    except Exception as exc:
        log.info("Docker local indisponível para autoatualização: %s", exc)
        return Capacidade(False, "docker_indisponivel")
    finally:
        await docker.aclose()


async def alvo_valido(versao: str, *, transport: httpx.AsyncBaseTransport | None = None) -> str:
    """Devolve a tag confirmada no registro, ou levanta.

    A versão pedida é conferida contra as tags publicadas e tem que ser maior que a atual. Uma
    rota que aceitasse referência de imagem arbitrária e a executasse com o socket do host seria
    execução remota de código com um nome bonito.
    """
    pedida = tupla(versao)
    if pedida is None:
        raise ValueError("versão inválida: use X.Y.Z")
    aqui = tupla(__version__)
    if aqui is not None and pedida <= aqui:
        raise ValueError(f"a versão {versao} não é mais nova que a {__version__}")
    async with httpx.AsyncClient(transport=transport) as cliente:
        publicadas = {t for t in await _tags(cliente) if tupla(t)}
    if versao not in publicadas:
        raise ValueError(f"a versão {versao} não está publicada no registro")
    return versao


@dataclass
class Progresso:
    """Onde a troca está. Em memória: o processo que a acompanha morre junto com ela."""

    versao: str
    fase: str
    erro: str | None = None


_progresso: Progresso | None = None
_tarefa: asyncio.Task[None] | None = None


def progresso() -> Progresso | None:
    return _progresso


async def atualizar(versao: str, *, socket: str | None = None) -> str:
    """Baixa a imagem e sobe o auxiliar que faz a troca. Devolve o id do auxiliar.

    A imagem é baixada **antes** de qualquer coisa ser tocada: `pull` que falha deixa o mundo
    exatamente como estava, e o erro vira estado visível em vez de contêiner parado.
    """
    global _progresso
    from lognix.updates.docker import AUXILIAR, DockerError, abrir

    quem = await capacidade(socket)
    if not quem.pode or not quem.container or not quem.nome:
        raise RuntimeError(quem.motivo)

    docker = abrir(socket)
    try:
        # Auxiliar em execução é uma troca em curso. Removê-lo à força mataria a sequência no
        # meio, e sobraria um contêiner renomeado e parado sem ninguém para devolvê-lo.
        try:
            anterior = await docker.inspecionar(AUXILIAR)
            if (anterior.get("State") or {}).get("Running"):
                raise RuntimeError("troca_em_andamento")
            await docker.remover(AUXILIAR, forcar=True)
        except DockerError:
            # Não existe auxiliar anterior: é o caso comum da primeira atualização.
            pass

        _progresso = Progresso(versao=versao, fase="baixando")
        log.info("baixando %s:%s", IMAGEM, versao)
        await docker.baixar(IMAGEM, versao)
        _progresso = Progresso(versao=versao, fase="trocando")

        auxiliar = await docker.criar(
            AUXILIAR,
            {
                "Image": f"{IMAGEM}:{versao}",
                "Cmd": [
                    "python",
                    "-m",
                    "lognix.updates.swap",
                    "--container",
                    quem.container,
                    "--nome",
                    quem.nome,
                    "--imagem",
                    f"{IMAGEM}:{versao}",
                ],
                # Tty para os registros voltarem como texto, sem a multiplexação do Docker.
                "Tty": True,
                "Labels": {"org.lognix.role": "updater"},
                "HostConfig": {
                    "Binds": [f"{docker.socket}:/var/run/docker.sock"],
                    # Sem rede: o trabalho é todo pelo socket, e quem baixa imagem é o daemon.
                    "NetworkMode": "none",
                    "RestartPolicy": {"Name": "no"},
                    # Precisa ser root para falar com o socket; é um contêiner de uma tarefa só.
                    "AutoRemove": False,
                },
                "User": "0:0",
            },
        )
        await docker.iniciar(auxiliar)
        log.warning("auxiliar de atualização iniciado para a versão %s", versao)
        return auxiliar
    finally:
        await docker.aclose()


async def disparar(versao: str, *, socket: str | None = None) -> None:
    """Põe a troca para rodar sem segurar a resposta.

    O `pull` de uma imagem multi-arquitetura leva minutos, e uma requisição aberta esse tempo
    todo morre em qualquer proxy no caminho — e o 504 convida ao clique de novo, que é
    exatamente o que não pode acontecer no meio de uma troca.
    """
    global _progresso

    async def tarefa() -> None:
        global _progresso
        try:
            await atualizar(versao, socket=socket)
        except Exception as exc:
            log.exception("a atualização para %s falhou antes de trocar", versao)
            _progresso = Progresso(versao=versao, fase="falhou", erro=str(exc))

    _progresso = Progresso(versao=versao, fase="baixando")
    # Referência guardada: tarefa sem dono pode ser coletada no meio pelo garbage collector.
    global _tarefa
    _tarefa = asyncio.create_task(tarefa())


@dataclass(frozen=True)
class Tentativa:
    estado: str
    codigo: int | None
    terminou_em: str | None
    registros: str


async def ultima_tentativa(socket: str | None = None) -> Tentativa | None:
    """Como terminou a última troca, lida do contêiner auxiliar que ficou para trás.

    É isso que permite ao Lognix novo contar, na tela, o fim de uma atualização que derrubou a
    tela — inclusive quando ela falhou e o antigo voltou.
    """
    from lognix.updates.docker import AUXILIAR, abrir

    docker = abrir(socket)
    try:
        dados = await docker.inspecionar(AUXILIAR)
        if not dados:
            return None
        estado = dados.get("State") or {}
        return Tentativa(
            estado=str(estado.get("Status") or "desconhecido"),
            codigo=estado.get("ExitCode"),
            terminou_em=estado.get("FinishedAt"),
            registros=await docker.registros(AUXILIAR),
        )
    except Exception:
        return None
    finally:
        await docker.aclose()
