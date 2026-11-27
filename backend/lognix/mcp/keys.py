"""Criação, verificação e revogação de chaves do MCP. Ver ADR 017.

A chave é tratada como senha: guardada com hash, mostrada uma vez. O prefixo em claro existe só
para a pessoa reconhecer na lista qual chave é qual — sem ele, revogar a certa vira adivinhação.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.mcp.models import McpCall, McpKey, McpScope
from lognix.security.passwords import hash_password, verify_password

log = logging.getLogger(__name__)

#: Prefixo reconhecível, para a chave ser identificável num log ou num `git grep` de vazamento.
PREFIXO = "lgxmcp_"
#: 32 bytes em base64url. Força de sobra, e cabe numa variável de ambiente sem quebrar linha.
BYTES = 32


def gerar() -> tuple[str, str]:
    """Devolve (chave completa, prefixo para exibição)."""
    segredo = secrets.token_urlsafe(BYTES)
    chave = f"{PREFIXO}{segredo}"
    return chave, chave[: len(PREFIXO) + 6]


async def criar(
    db: AsyncSession,
    *,
    nome: str,
    escopos: list[McpScope],
    expira_em: datetime | None = None,
    criada_por: uuid.UUID | None = None,
) -> tuple[McpKey, str]:
    """Cria a chave e devolve o valor em claro — a única vez que ele existe fora do hash."""
    chave, prefixo = gerar()
    registro = McpKey(
        name=nome.strip(),
        prefix=prefixo,
        key_hash=hash_password(chave),
        scopes=sorted({str(e) for e in escopos}),
        expires_at=expira_em,
        created_by=criada_por,
    )
    db.add(registro)
    await db.commit()
    await db.refresh(registro)
    log.info("chave MCP criada", extra={"chave": registro.name, "escopos": registro.scopes})
    return registro, chave


async def verificar(db: AsyncSession, chave: str) -> McpKey | None:
    """Encontra a chave ativa correspondente, ou `None`.

    O prefixo estreita a busca para uma linha, mas a decisão é sempre do hash: comparar prefixo
    não autentica ninguém. Chave desativada ou vencida não entra, e isso é checado aqui e não na
    consulta, para que expiração e revogação tenham o mesmo caminho.
    """
    if not chave.startswith(PREFIXO):
        return None
    prefixo = chave[: len(PREFIXO) + 6]
    candidatas = list((await db.execute(select(McpKey).where(McpKey.prefix == prefixo))).scalars())
    agora = datetime.now(UTC)
    for registro in candidatas:
        if verify_password(registro.key_hash, chave) and registro.ativa(agora):
            return registro
    return None


async def registrar_uso(
    db: AsyncSession,
    registro: McpKey | None,
    *,
    tool: str,
    ok: bool,
    duracao_ms: int,
    erro: str | None = None,
) -> None:
    """Anota a chamada e carimba o último uso da chave."""
    db.add(
        McpCall(
            key_id=registro.id if registro else None,
            key_name=registro.name if registro else "",
            tool=tool,
            ok=ok,
            error=(erro or None) and erro[:300],
            duration_ms=duracao_ms,
        )
    )
    if registro is not None:
        registro.last_used_at = datetime.now(UTC)
        registro.calls = (registro.calls or 0) + 1
    await db.commit()
