"""Esquema fechado da resposta da IA. Fora do esquema é retry. Pipeline seção 5 e 6."""

from __future__ import annotations

from typing import Any

INSIGHT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "severity",
        "title",
        "summary",
        "probable_cause",
        "suggested_action",
        "evidence_refs",
        "confidence",
        "needs_code",
    ],
    "properties": {
        "severity": {"enum": ["critical", "high", "medium", "low", "info"]},
        "title": {"type": "string", "maxLength": 120},
        "summary": {"type": "string", "maxLength": 1200},
        "probable_cause": {"type": "string", "maxLength": 1200},
        "suggested_action": {"type": "string", "maxLength": 800},
        "evidence_refs": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "index"],
                "properties": {
                    "kind": {"enum": ["log_line", "docker_event", "pattern"]},
                    "index": {"type": "integer", "minimum": 0},
                },
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "needs_code": {"type": "boolean"},
    },
}

_SEVERITIES = {"critical", "high", "medium", "low", "info"}
_KINDS = {"log_line", "docker_event", "pattern"}


class SchemaError(ValueError):
    """Resposta fora do esquema. A mensagem vai no retry para o modelo se corrigir."""


def _text(data: dict[str, Any], key: str, max_len: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"campo '{key}' ausente ou vazio")
    if len(value) > max_len:
        raise SchemaError(f"campo '{key}' excede {max_len} caracteres")
    return value.strip()


def validate_insight(data: Any, *, max_index: dict[str, int]) -> dict[str, Any]:
    """Valida contra o esquema e confere que os índices de evidência existem no contexto."""
    if not isinstance(data, dict):
        raise SchemaError("a resposta não é um objeto JSON")
    extra = set(data) - set(INSIGHT_SCHEMA["properties"])
    if extra:
        raise SchemaError(f"campos não previstos: {', '.join(sorted(extra))}")

    severity = data.get("severity")
    if severity not in _SEVERITIES:
        raise SchemaError(f"'severity' precisa ser um de {sorted(_SEVERITIES)}")

    out: dict[str, Any] = {
        "severity": severity,
        "title": _text(data, "title", 120),
        "summary": _text(data, "summary", 1200),
        "probable_cause": _text(data, "probable_cause", 1200),
        "suggested_action": _text(data, "suggested_action", 800),
    }

    confidence = data.get("confidence")
    if not isinstance(confidence, int | float) or isinstance(confidence, bool):
        raise SchemaError("'confidence' precisa ser um número entre 0 e 1")
    if not 0 <= float(confidence) <= 1:
        raise SchemaError("'confidence' precisa estar entre 0 e 1")
    out["confidence"] = round(float(confidence), 2)

    needs_code = data.get("needs_code")
    if not isinstance(needs_code, bool):
        raise SchemaError("'needs_code' precisa ser true ou false")
    out["needs_code"] = needs_code

    refs = data.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        raise SchemaError("'evidence_refs' precisa ter ao menos uma evidência")
    if len(refs) > 20:
        raise SchemaError("'evidence_refs' aceita no máximo 20 itens")
    clean: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            raise SchemaError("cada evidência precisa ser um objeto com 'kind' e 'index'")
        kind, index = ref.get("kind"), ref.get("index")
        if kind not in _KINDS:
            raise SchemaError(f"'kind' precisa ser um de {sorted(_KINDS)}")
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise SchemaError("'index' precisa ser um inteiro não negativo")
        limit = max_index.get(str(kind), 0)
        if index >= limit:
            raise SchemaError(
                f"evidência {kind}[{index}] não existe no contexto; "
                f"os índices válidos de {kind} vão de 0 a {max(limit - 1, 0)}"
            )
        clean.append({"kind": kind, "index": index})
    out["evidence_refs"] = clean
    return out
