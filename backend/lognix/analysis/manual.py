"""Limite da análise sob demanda, compartilhado pela interface e pelo MCP.

Uma por minuto por projeto. O limite mora aqui, e não na rota, porque desde a 1.1.0 há dois
caminhos até o mesmo ciclo: se cada um guardasse o seu contador, um cliente MCP dobraria o
limite só por entrar por outra porta.
"""

from __future__ import annotations

import time
import uuid

INTERVALO_MINIMO = 60

_ultima: dict[uuid.UUID, float] = {}


def espera(projeto: uuid.UUID) -> float:
    """Segundos que faltam para o projeto poder ser analisado de novo. 0 significa agora."""
    ultima = _ultima.get(projeto)
    if ultima is None:
        return 0.0
    return max(0.0, INTERVALO_MINIMO - (time.monotonic() - ultima))


def marcar(projeto: uuid.UUID) -> None:
    _ultima[projeto] = time.monotonic()


def limpar() -> None:
    """Só para os testes, que rodam várias análises do mesmo projeto em segundos."""
    _ultima.clear()
