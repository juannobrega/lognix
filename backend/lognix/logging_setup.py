"""Logs do próprio Lognix em JSON para stdout."""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "{asctime}{levelname}{name}{message}",
            style="{",
            rename_fields={"asctime": "time", "levelname": "level", "name": "logger"},
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # O asyncssh registra em INFO cada canal aberto e fechado. Com um túnel por host e uma
    # conexão por requisição à Docker API, isso domina o log e esconde o que importa.
    logging.getLogger("asyncssh").setLevel(logging.WARNING)
