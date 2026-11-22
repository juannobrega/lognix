"""Classificação de nível de uma linha: campo de nível em JSON, senão regex. Única implementação."""

from __future__ import annotations

import json
import re

from lognix.analysis.models import LogLevel

LEVEL_KEYS = ("level", "lvl", "severity", "log.level", "loglevel", "log_level", "@l")

_LEVEL_MAP = {
    "fatal": LogLevel.error,
    "critical": LogLevel.error,
    "crit": LogLevel.error,
    "emerg": LogLevel.error,
    "alert": LogLevel.error,
    "panic": LogLevel.error,
    "error": LogLevel.error,
    "err": LogLevel.error,
    "warning": LogLevel.warn,
    "warn": LogLevel.warn,
    "info": LogLevel.info,
    "information": LogLevel.info,
    "notice": LogLevel.info,
    "debug": LogLevel.debug,
    "trace": LogLevel.debug,
    "verbose": LogLevel.debug,
}

# Texto livre. Versionado: mudar aqui muda a classificação de todo o sistema.
ERROR_RE = re.compile(
    r"(?:\b(?:ERROR|FATAL|CRITICAL|PANIC|EMERG|ALERT|Exception|Traceback|panic)\b"
    r"|\[(?:error|crit|emerg|alert)\]|\bERR\b|\blevel=(?:error|fatal|critical)\b"
    r"|\bexited with code [1-9]|\bsegmentation fault\b|\bOOMKilled\b)",
)
WARN_RE = re.compile(r"(?:\b(?:WARN|WARNING)\b|\[warn(?:ing)?\]|\blevel=warn(?:ing)?\b)")
INFO_RE = re.compile(r"(?:\bINFO\b|\[info\]|\blevel=info\b|\bNOTICE\b)")
DEBUG_RE = re.compile(r"(?:\bDEBUG\b|\bTRACE\b|\[debug\]|\blevel=(?:debug|trace)\b)")


def _structured_level(line: str) -> LogLevel | None:
    stripped = line.lstrip()
    if not stripped.startswith("{"):
        return None
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    for key in LEVEL_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value:
            return _LEVEL_MAP.get(value.strip().lower(), LogLevel.unknown)
        if isinstance(value, int):  # níveis numéricos (pino/bunyan): >=50 error, 40 warn, 30 info
            if value >= 50:
                return LogLevel.error
            if value >= 40:
                return LogLevel.warn
            if value >= 30:
                return LogLevel.info
            return LogLevel.debug
    return None


def classify(line: str) -> LogLevel:
    level = _structured_level(line)
    if level is not None:
        return level
    head = line[:400]
    if ERROR_RE.search(head):
        return LogLevel.error
    if WARN_RE.search(head):
        return LogLevel.warn
    if INFO_RE.search(head):
        return LogLevel.info
    if DEBUG_RE.search(head):
        return LogLevel.debug
    return LogLevel.unknown
