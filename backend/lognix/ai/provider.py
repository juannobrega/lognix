"""Interface única de provider de IA. O resto do backend não conhece OpenRouter."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from lognix.ai.models import CostSource


class AiError(Exception):
    """Falha ao falar com o provider. `retryable` distingue rede de recusa definitiva."""

    def __init__(self, message: str, *, retryable: bool = False, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.status = status


class RateLimitedError(AiError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message, retryable=True, status=429)
        self.retry_after = retry_after


@dataclass
class AiResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal(0)
    cost_source: CostSource = CostSource.unknown
    latency_ms: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    context_length: int | None = None
    prompt_usd_per_mtok: float | None = None
    completion_usd_per_mtok: float | None = None


class AiProvider(Protocol):
    name: str

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None,
        model: str,
        max_output_tokens: int,
    ) -> AiResult: ...

    async def models(self) -> list[ModelInfo]: ...

    async def aclose(self) -> None: ...
