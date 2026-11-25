"""Tipos de provider e a fábrica que monta um a partir da configuração guardada."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

from lognix.ai.provider import AiError, AiProvider

if TYPE_CHECKING:
    import httpx


class ProviderKind(enum.StrEnum):
    openrouter = "openrouter"
    openai = "openai"
    bedrock = "bedrock"


#: Campos de credencial por tipo. `secret` nunca volta pela API.
CREDENTIAL_FIELDS: dict[ProviderKind, list[dict[str, Any]]] = {
    ProviderKind.openrouter: [
        {
            "key": "api_key",
            "label": "Chave de API",
            "secret": True,
            "required": True,
            "placeholder": "sk-or-v1-…",
            "help": "Gerada em openrouter.ai/keys.",
        },
        {
            "key": "base_url",
            "label": "URL base",
            "secret": False,
            "required": False,
            "placeholder": "https://openrouter.ai/api/v1",
            "help": "Mude apenas se usa um proxy compatível.",
        },
    ],
    ProviderKind.openai: [
        {
            "key": "api_key",
            "label": "Chave de API",
            "secret": True,
            "required": True,
            "placeholder": "sk-…",
            "help": "Gerada em platform.openai.com/api-keys.",
        },
        {
            "key": "base_url",
            "label": "URL base",
            "secret": False,
            "required": False,
            "placeholder": "https://api.openai.com/v1",
            "help": "Para Azure OpenAI ou um gateway compatível.",
        },
        {
            "key": "organization",
            "label": "Organização",
            "secret": False,
            "required": False,
            "placeholder": "org-…",
            "help": "Opcional, se sua conta tem várias.",
        },
    ],
    ProviderKind.bedrock: [
        {
            "key": "region",
            "label": "Região",
            "secret": False,
            "required": True,
            "placeholder": "us-east-1",
            "help": "Onde os modelos estão habilitados na sua conta.",
        },
        {
            "key": "access_key_id",
            "label": "Access key ID",
            "secret": False,
            "required": True,
            "placeholder": "AKIA…",
            "help": "De um usuário IAM com bedrock:InvokeModel.",
        },
        {
            "key": "secret_access_key",
            "label": "Secret access key",
            "secret": True,
            "required": True,
            "placeholder": "…",
            "help": "Guardada criptografada.",
        },
        {
            "key": "session_token",
            "label": "Session token",
            "secret": True,
            "required": False,
            "placeholder": "…",
            "help": "Só para credenciais temporárias.",
        },
    ],
}

PROVIDER_LABEL: dict[ProviderKind, str] = {
    ProviderKind.openrouter: "OpenRouter",
    ProviderKind.openai: "OpenAI",
    ProviderKind.bedrock: "Amazon Bedrock",
}

#: Quem consegue listar o catálogo de modelos sozinho.
HAS_CATALOG: dict[ProviderKind, bool] = {
    ProviderKind.openrouter: True,
    ProviderKind.openai: True,
    ProviderKind.bedrock: True,
}


def build_provider(
    kind: ProviderKind | str,
    credentials: dict[str, Any],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AiProvider:
    """Monta o provider a partir do tipo e das credenciais já descriptografadas."""
    from lognix.ai.providers.bedrock import BedrockProvider
    from lognix.ai.providers.openai import OpenAiProvider
    from lognix.ai.providers.openrouter import OpenRouterProvider

    kind = ProviderKind(kind)
    missing = [
        f["label"]
        for f in CREDENTIAL_FIELDS[kind]
        if f["required"] and not str(credentials.get(f["key"]) or "").strip()
    ]
    if missing:
        raise AiError(f"Falta preencher: {', '.join(missing)}.")

    if kind == ProviderKind.openrouter:
        return OpenRouterProvider(
            credentials["api_key"],
            base_url=credentials.get("base_url") or None,
            transport=transport,
        )
    if kind == ProviderKind.openai:
        return OpenAiProvider(
            credentials["api_key"],
            base_url=credentials.get("base_url") or None,
            organization=credentials.get("organization") or None,
            transport=transport,
        )
    return BedrockProvider(
        region=credentials["region"],
        access_key_id=credentials["access_key_id"],
        secret_access_key=credentials["secret_access_key"],
        session_token=credentials.get("session_token") or None,
        transport=transport,
    )
