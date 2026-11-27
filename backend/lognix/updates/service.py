"""Descobre se existe versão nova publicada. Ver ADR 018.

Desligada por padrão: verificar atualização é uma chamada para fora, e a documentação do produto
promete não fazer nenhuma sem que a pessoa peça.

A fonte é a lista de tags do GHCR, e não a API de releases do GitHub, porque o que interessa é a
versão que dá para **baixar**. As duas já divergiram aqui: a v1.1.0 teve tag e release sem imagem
publicada, porque o build foi cancelado. Anunciar versão cujo `docker pull` falha é pior que não
anunciar nada.
"""

from __future__ import annotations

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
