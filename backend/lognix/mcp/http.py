"""Montagem HTTP do servidor MCP. Ver ADR 017."""

from __future__ import annotations

from functools import cache

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.types import ASGIApp, Receive, Scope, Send

from lognix.config import get_settings
from lognix.mcp.server import construir


def _seguranca() -> TransportSecuritySettings:
    """Proteção contra DNS rebinding com os nomes desta instalação.

    O padrão do SDK só aceita 127.0.0.1, o que responderia 421 em qualquer instalação com
    domínio próprio. Os nomes vêm de LOGNIX_PUBLIC_URL, e LOGNIX_MCP_ALLOWED_HOSTS="*"
    desliga a checagem para quem publica o Lognix por mais de um nome atrás de proxy.
    """
    cfg = get_settings()
    hosts = cfg.mcp_hosts
    if not hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return TransportSecuritySettings(
        allowed_hosts=hosts,
        allowed_origins=[cfg.lognix_public_url.rstrip("/")],
    )


class _NaRaiz:
    """Entrega a requisição ao app do MCP como se ela tivesse chegado em "/".

    Serve à rota exata `/mcp`: um `Mount("/mcp")` casa só `/mcp/...`, e o roteador responderia
    307 para `/mcp/`. Cliente MCP manda POST, e POST redirecionado é algo que boa parte dos
    clientes HTTP não repete — a sessão morreria no redirecionamento. Como a tela mostra o
    endereço sem barra, `/mcp` precisa atender direto.

    Classe, e não função: o `Route` do Starlette trata função como manipulador de
    requisição e resposta, e aí só o GET passaria.
    """

    def __init__(self, alvo: ASGIApp) -> None:
        self.alvo = alvo

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.alvo({**scope, "path": "/", "raw_path": b"/"}, receive, send)


@cache
def _servidor() -> Starlette:
    """App do transporte Streamable HTTP, uma instância por processo.

    O caminho interno é "/" porque o prefixo quem dá é a montagem em /mcp — deixar "/mcp"
    nos dois lugares atenderia em /mcp/mcp. Instância única porque o ciclo de vida e a
    montagem precisam falar do mesmo gerenciador de sessões: o do SDK só aceita um `run()`.
    """
    return construir().streamable_http_app(
        streamable_http_path="/",
        transport_security=_seguranca(),
    )


def app_mcp() -> Starlette:
    """O app do MCP. Vai montado em /mcp, e é dele o lifespan que o Mount não propaga."""
    return _servidor()


def rota_exata() -> ASGIApp:
    """Atende `/mcp` sem barra final, sem redirecionamento. Ver `_NaRaiz`."""
    return _NaRaiz(_servidor())
