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
    kind = "openrouter"
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

    async def test(self, model: str) -> AiResult:
        return await self.complete(
            system="Responda exatamente: ok",
            user="ok",
            schema=None,
            model=model,
            max_output_tokens=16,
        )

    async def models(self) -> list[ModelInfo]:
        return self.model_list

    async def aclose(self) -> None:
        self.closed = True


class FakeRuntime:
    """Substitui o AiRuntime: devolve uma cadeia de providers falsos, na ordem dada."""

    def __init__(self, *providers: FakeAiProvider, model: str = "fake/model") -> None:
        import asyncio
        import uuid as _uuid

        from lognix.ai.models import AiProviderConfig

        self.providers = list(providers)
        self.model = model
        self.enabled = True
        self._paused: dict[Any, Any] = {}
        self._semaphore = asyncio.Semaphore(3)
        self.configs = [
            AiProviderConfig(
                id=_uuid.uuid4(),
                kind=p.kind,
                name=f"fake-{i}",
                enabled=True,
                priority=i,
                default_model=model,
            )
            for i, p in enumerate(self.providers)
        ]
        self._by_id = dict(zip([c.id for c in self.configs], self.providers, strict=True))

    async def chain(self, db: Any) -> list[Any]:
        from lognix.ai.service import AiDisabledError, AiPausedError

        if not self.enabled or not self.configs:
            raise AiDisabledError
        available = [c for c in self.configs if self.paused_until(c.id) is None]
        if not available:
            raise AiPausedError(min(self._paused.values()))
        return available

    def provider_for_config(self, config: Any) -> FakeAiProvider:
        return self._by_id[config.id]

    @property
    def semaphore(self) -> Any:
        return self._semaphore

    def pause(self, provider_id: Any, seconds: float | None = None) -> None:
        from datetime import UTC, datetime, timedelta

        self._paused[provider_id] = datetime.now(UTC) + timedelta(seconds=seconds or 300)

    def paused_until(self, provider_id: Any) -> Any:
        return self._paused.get(provider_id)

    def paused_all(self) -> dict[str, Any]:
        return {str(k): v for k, v in self._paused.items()}

    async def reset(self) -> None:
        self._paused.clear()

    async def install(self) -> None:
        """Grava os providers falsos no banco: AiCall tem chave estrangeira para eles."""
        from lognix.db import get_sessionmaker

        async with get_sessionmaker()() as db:
            for config in self.configs:
                db.add(config)
            await db.commit()
            for config in self.configs:
                db.expunge(config)


def error(message: str, **kw: Any) -> AiError:
    return AiError(message, **kw)
