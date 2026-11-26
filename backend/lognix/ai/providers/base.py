"""Tipos de provider e a fábrica que monta um a partir da configuração guardada.

A maioria dos serviços fala o mesmo dialeto da API de chat da OpenAI e se distingue só pela URL
base. Por isso a lista aqui é **dado**, não código: acrescentar um desses é uma entrada em `SPECS`.
Só quem tem protocolo próprio — Anthropic e Bedrock — ganha implementação.

As URLs foram conferidas uma a uma contra o serviço real: um `GET` sem credencial no caminho de
catálogo tem que responder 401/403, não 404. Ver `Planning > 04 Inteligência Artificial >
Providers`.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lognix.ai.provider import AiError, AiProvider

if TYPE_CHECKING:
    import httpx


class ProviderKind(enum.StrEnum):
    openrouter = "openrouter"
    openai = "openai"
    bedrock = "bedrock"
    anthropic = "anthropic"
    gemini = "gemini"
    groq = "groq"
    mistral = "mistral"
    deepseek = "deepseek"
    xai = "xai"
    together = "together"
    fireworks = "fireworks"
    cerebras = "cerebras"
    perplexity = "perplexity"
    ollama = "ollama"
    custom = "custom"


def _api_key(placeholder: str, help_text: str, *, required: bool = True) -> dict[str, Any]:
    return {
        "key": "api_key",
        "label": "Chave de API",
        "secret": True,
        "required": required,
        "placeholder": placeholder,
        "help": help_text,
    }


def _base_url(default: str, *, required: bool = False) -> dict[str, Any]:
    return {
        "key": "base_url",
        "label": "URL base",
        "secret": False,
        "required": required,
        "placeholder": default,
        "help": "Mude só se você usa um proxy ou gateway compatível."
        if not required
        else "Endereço do seu servidor.",
    }


@dataclass(frozen=True)
class ProviderSpec:
    kind: ProviderKind
    label: str
    fields: list[dict[str, Any]]
    #: Fala o dialeto de chat da OpenAI nesta URL. `None` quando tem protocolo próprio.
    base_url: str | None = None
    #: Consegue listar os próprios modelos. Quando falso, o cadastro é à mão.
    has_catalog: bool = True
    #: Onde o usuário consegue a credencial.
    docs: str = ""
    notes: str = ""
    aliases: list[str] = field(default_factory=list)


def _openai_like(
    kind: ProviderKind,
    label: str,
    base_url: str,
    docs: str,
    *,
    has_catalog: bool = True,
    key_placeholder: str = "…",
    key_required: bool = True,
    notes: str = "",
) -> ProviderSpec:
    return ProviderSpec(
        kind=kind,
        label=label,
        base_url=base_url,
        has_catalog=has_catalog,
        docs=docs,
        notes=notes,
        fields=[
            _api_key(key_placeholder, f"Gerada em {docs}.", required=key_required),
            _base_url(base_url, required=not key_required),
        ],
    )


SPECS: dict[ProviderKind, ProviderSpec] = {
    ProviderKind.openrouter: _openai_like(
        ProviderKind.openrouter,
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        "openrouter.ai/keys",
        key_placeholder="sk-or-v1-…",
        notes="Único que devolve o custo real de cada chamada na própria resposta.",
    ),
    ProviderKind.openai: ProviderSpec(
        kind=ProviderKind.openai,
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        docs="platform.openai.com/api-keys",
        fields=[
            _api_key("sk-…", "Gerada em platform.openai.com/api-keys."),
            _base_url("https://api.openai.com/v1"),
            {
                "key": "organization",
                "label": "Organização",
                "secret": False,
                "required": False,
                "placeholder": "org-…",
                "help": "Opcional, se sua conta tem várias.",
            },
        ],
    ),
    ProviderKind.anthropic: ProviderSpec(
        kind=ProviderKind.anthropic,
        label="Anthropic",
        base_url=None,  # protocolo próprio: /v1/messages
        docs="console.anthropic.com/settings/keys",
        fields=[_api_key("sk-ant-…", "Gerada em console.anthropic.com/settings/keys.")],
        notes="API de mensagens própria, não a de chat da OpenAI.",
    ),
    ProviderKind.bedrock: ProviderSpec(
        kind=ProviderKind.bedrock,
        label="Amazon Bedrock",
        base_url=None,  # protocolo próprio: Converse API com assinatura SigV4
        # Lista os foundation models habilitados na conta, pelo control plane.
        docs="console.aws.amazon.com/bedrock",
        notes="Não informa custo na resposta: cadastre o preço do modelo para estimar o gasto.",
        fields=[
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
    ),
    ProviderKind.gemini: _openai_like(
        ProviderKind.gemini,
        "Google Gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "aistudio.google.com/apikey",
        # Conferido: o caminho de compatibilidade atende /chat/completions mas devolve 404 em
        # /models. Sem catálogo, então, mesmo o serviço tendo um na API nativa.
        has_catalog=False,
        key_placeholder="AIza…",
        notes="A camada compatível não publica catálogo: cadastre o modelo à mão.",
    ),
    ProviderKind.groq: _openai_like(
        ProviderKind.groq,
        "Groq",
        "https://api.groq.com/openai/v1",
        "console.groq.com/keys",
        key_placeholder="gsk_…",
    ),
    ProviderKind.mistral: _openai_like(
        ProviderKind.mistral,
        "Mistral",
        "https://api.mistral.ai/v1",
        "console.mistral.ai/api-keys",
    ),
    ProviderKind.deepseek: _openai_like(
        ProviderKind.deepseek,
        "DeepSeek",
        "https://api.deepseek.com/v1",
        "platform.deepseek.com/api_keys",
        key_placeholder="sk-…",
    ),
    ProviderKind.xai: _openai_like(
        ProviderKind.xai,
        "xAI",
        "https://api.x.ai/v1",
        "console.x.ai",
        key_placeholder="xai-…",
    ),
    ProviderKind.together: _openai_like(
        ProviderKind.together,
        "Together AI",
        "https://api.together.xyz/v1",
        "api.together.ai/settings/api-keys",
    ),
    ProviderKind.fireworks: _openai_like(
        ProviderKind.fireworks,
        "Fireworks AI",
        "https://api.fireworks.ai/inference/v1",
        "fireworks.ai/account/api-keys",
    ),
    ProviderKind.cerebras: _openai_like(
        ProviderKind.cerebras,
        "Cerebras",
        "https://api.cerebras.ai/v1",
        "cloud.cerebras.ai",
        key_placeholder="csk-…",
    ),
    ProviderKind.perplexity: _openai_like(
        ProviderKind.perplexity,
        "Perplexity",
        "https://api.perplexity.ai",
        "perplexity.ai/settings/api",
        # Conferido: atende /chat/completions e não expõe /models.
        has_catalog=False,
        key_placeholder="pplx-…",
        notes="Não publica catálogo: cadastre o modelo à mão.",
    ),
    # Qualquer serviço que fale o dialeto da OpenAI e não esteja na lista: um gateway interno,
    # um provedor regional, um vLLM próprio. É a válvula de escape para não precisar de release
    # do Lognix só para acrescentar uma URL.
    ProviderKind.custom: ProviderSpec(
        kind=ProviderKind.custom,
        label="Compatível com OpenAI",
        base_url="",  # sempre vem do usuário
        docs="",
        notes="Para qualquer serviço que exponha /chat/completions no formato da OpenAI. "
        "O catálogo aparece se o serviço responder em /models.",
        fields=[
            _base_url("https://meu-gateway.exemplo/v1", required=True),
            _api_key("…", "Deixe em branco se o serviço não exige credencial.", required=False),
        ],
    ),
    ProviderKind.ollama: _openai_like(
        ProviderKind.ollama,
        "Ollama",
        "http://localhost:11434/v1",
        "ollama.com",
        key_required=False,
        notes="Roda na sua máquina, sem custo por token. O endereço precisa ser alcançável "
        "de dentro do contêiner do Lognix: use o IP do host, não localhost.",
    ),
}

#: Campos de credencial por tipo. `secret` nunca volta pela API.
CREDENTIAL_FIELDS: dict[ProviderKind, list[dict[str, Any]]] = {
    k: s.fields for k, s in SPECS.items()
}
PROVIDER_LABEL: dict[ProviderKind, str] = {k: s.label for k, s in SPECS.items()}
#: Quem consegue listar o catálogo de modelos sozinho.
HAS_CATALOG: dict[ProviderKind, bool] = {k: s.has_catalog for k, s in SPECS.items()}


def build_provider(
    kind: ProviderKind | str,
    credentials: dict[str, Any],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AiProvider:
    """Monta o provider a partir do tipo e das credenciais já descriptografadas."""
    from lognix.ai.providers.anthropic import AnthropicProvider
    from lognix.ai.providers.bedrock import BedrockProvider
    from lognix.ai.providers.openai import OpenAiProvider
    from lognix.ai.providers.openrouter import OpenRouterProvider

    kind = ProviderKind(kind)
    spec = SPECS[kind]
    missing = [
        f["label"]
        for f in spec.fields
        if f["required"] and not str(credentials.get(f["key"]) or "").strip()
    ]
    if missing:
        raise AiError(f"Falta preencher: {', '.join(missing)}.")

    if kind == ProviderKind.bedrock:
        return BedrockProvider(
            region=credentials["region"],
            access_key_id=credentials["access_key_id"],
            secret_access_key=credentials["secret_access_key"],
            session_token=credentials.get("session_token") or None,
            transport=transport,
        )
    if kind == ProviderKind.anthropic:
        return AnthropicProvider(credentials["api_key"], transport=transport)
    if kind == ProviderKind.openrouter:
        return OpenRouterProvider(
            credentials["api_key"],
            base_url=credentials.get("base_url") or None,
            transport=transport,
        )
    # Todo o resto fala o dialeto da OpenAI; muda a URL, a chave e o nome nos erros.
    return OpenAiProvider(
        credentials.get("api_key") or "",
        base_url=credentials.get("base_url") or spec.base_url,
        organization=credentials.get("organization") or None,
        transport=transport,
        kind=str(kind),
        name=spec.label,
    )
