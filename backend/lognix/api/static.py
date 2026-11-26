"""Serve o frontend construído, no mesmo processo da API.

Existe porque frontend e backend viraram uma imagem só (ADR 013): duas imagens para manter na mesma
versão é um jeito conhecido de alguém acabar com a tela nova falando com a API velha.

Herda do nginx que estava aqui antes três comportamentos que não são detalhe:

1. **Arquivo com hash no nome que não existe responde 404**, não o `index.html`. O fallback de SPA
   pegando tudo fazia um browser com o index antigo em cache pedir um bundle que saiu no deploy
   anterior, receber HTML com status 200, não conseguir parsear o módulo e mostrar tela branca —
   sem erro de rede e sem log no servidor.
2. **Duas políticas de cache opostas**: o `index.html` tem nome fixo e conteúdo novo a cada versão,
   então `no-cache`; os arquivos com hash nunca mudam, então `immutable` por um ano.
3. **Cabeçalhos de segurança em toda resposta**, inclusive nas da API.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

log = logging.getLogger(__name__)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'"
    ),
}
#: Só para nome com hash: o conteúdo daquela URL nunca muda.
IMMUTABLE = "public, max-age=31536000, immutable"
#: Para tudo que tem nome fixo — index.html, favicon, logo. Revalida sempre, e um 304 é barato.
#: Marcar um logo sem hash como imutável prenderia a troca de arte por um ano no browser de quem
#: já visitou.
NO_CACHE = "no-cache"


class _Assets(StaticFiles):
    """Arquivos com hash no nome: cacheáveis para sempre, e 404 de verdade quando não existem."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = IMMUTABLE
        return response


def mount_frontend(app: FastAPI, directory: Path) -> None:
    """Monta os estáticos. Sem o diretório, a API sobe sozinha — é o caso do desenvolvimento."""

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    index = directory / "index.html"
    if not index.is_file():
        log.warning("frontend não encontrado em %s: a API sobe sem interface", directory)
        return

    assets = directory / "assets"
    if assets.is_dir():
        app.mount("/assets", _Assets(directory=assets), name="assets")

    # HEAD junto com GET porque o nginx respondia aos dois, e quem faz HEAD numa página não é
    # browser: é verificador de link, proxy e health check. Devolver 405 para eles seria uma
    # regressão silenciosa da troca de servidor.
    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def spa(full_path: str) -> Response:
        """Qualquer caminho que não seja da API devolve o index: as rotas são do React."""
        # Arquivo real na raiz do build (favicon, logo, robots) é servido como está. Nome sem
        # hash, então nunca imutável.
        raiz = directory.resolve()
        candidate = (directory / full_path).resolve()
        if full_path and raiz in candidate.parents and candidate.is_file():
            return FileResponse(candidate, headers={"Cache-Control": NO_CACHE})
        return FileResponse(index, headers={"Cache-Control": NO_CACHE})
