"""Implementações de provider de IA. Cada uma fala com um serviço; nenhuma conhece as outras."""

from lognix.ai.providers.base import ProviderKind, build_provider
from lognix.ai.providers.bedrock import BedrockProvider
from lognix.ai.providers.openai import OpenAiProvider
from lognix.ai.providers.openrouter import OpenRouterProvider

__all__ = [
    "BedrockProvider",
    "OpenAiProvider",
    "OpenRouterProvider",
    "ProviderKind",
    "build_provider",
]
