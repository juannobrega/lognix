"""Provider de IA falso: responde o que o teste mandar, conta chamadas."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from lognix.ai.models import CostSource
from lognix.ai.provider import AiError, AiResult, ModelInfo

VALID_INSIGHT = {
    "severity": "high",
    "title": "Banco inacessível após redeploy",
    "summary": "O serviço perdeu a conexão com o Postgres logo depois de subir a nova imagem.",
    "probable_cause": "A nova imagem aponta para um host de banco que não resolve na rede.",
    "suggested_action": "Confira DATABASE_URL na nova imagem e a rede do compose.",
    "evidence_refs": [{"kind": "log_line", "index": 0}],
    "confidence": 0.82,
    "needs_code": False,
}


class FakeAiProvider:
    name = "fake"

    def __init__(self) -> None:
        self.responses: list[str | Exception] = []
        self.calls: list[dict[str, Any]] = []
        self.closed = False
        self.model_list = [
            ModelInfo("anthropic/claude-sonnet-4.5", "Claude Sonnet 4.5", 200000, 3.0, 15.0),
            ModelInfo("openai/gpt-5", "GPT-5", 400000, 1.25, 10.0),
        ]

    def reply(self, payload: dict[str, Any] | str | Exception) -> None:
        self.responses.append(
            payload if isinstance(payload, str | Exception) else json.dumps(payload)
        )

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None,
        model: str,
        max_output_tokens: int,
    ) -> AiResult:
        self.calls.append({"system": system, "user": user, "schema": schema, "model": model})
        if not self.responses:
            raise AssertionError("FakeAiProvider sem resposta programada")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return AiResult(
            text=item,
            model=model,
            input_tokens=max(1, len(user) // 4),
            output_tokens=max(1, len(item) // 4),
            cost_usd=Decimal("0.0042"),
            cost_source=CostSource.provider,
            latency_ms=123,
        )

    async def models(self) -> list[ModelInfo]:
        return self.model_list

    async def aclose(self) -> None:
        self.closed = True


class FakeRuntime:
    """Substitui o AiRuntime: devolve sempre o provider falso."""

    def __init__(self, provider: FakeAiProvider, model: str = "fake/model") -> None:
        self.provider = provider
        self.model = model
        self.enabled = True
        self._paused_until = None
        import asyncio

        self._semaphore = asyncio.Semaphore(3)

    async def provider_for(self, db: Any) -> tuple[FakeAiProvider, str]:
        from lognix.ai.service import AiDisabledError

        if not self.enabled:
            raise AiDisabledError
        return self.provider, self.model

    @property
    def semaphore(self) -> Any:
        return self._semaphore

    def pause(self, seconds: float | None = None) -> None:
        from datetime import UTC, datetime, timedelta

        self._paused_until = datetime.now(UTC) + timedelta(seconds=seconds or 300)

    @property
    def paused_until(self) -> Any:
        return self._paused_until

    async def reset(self) -> None:
        self._paused_until = None


def error(message: str, **kw: Any) -> AiError:
    return AiError(message, **kw)
