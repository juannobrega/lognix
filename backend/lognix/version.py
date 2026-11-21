"""Versão do Lognix.

Fonte de verdade: pyproject.toml na raiz do repositório. No build da imagem ela é
copiada para lognix/VERSION. Em desenvolvimento, lê-se a raiz diretamente.
"""

from __future__ import annotations

import re
from pathlib import Path


def _read_version() -> str:
    here = Path(__file__).resolve().parent
    baked = here / "VERSION"
    if baked.exists():
        return baked.read_text(encoding="utf-8").strip()
    root = here.parent.parent / "pyproject.toml"
    if root.exists():
        match = re.search(r'(?m)^version = "([^"]+)"', root.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return "0.0.0-dev"


__version__ = _read_version()
