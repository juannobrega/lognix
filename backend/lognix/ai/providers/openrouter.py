"""Implementação de AiProvider para o OpenRouter. ADR 006."""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

import httpx

from lognix.ai.models import CostSource
from lognix.ai.provider import AiError, AiResult, ModelInfo, RateLimitedError

log = logging.getLogger(__name__)

BASE_URL = "https://openrouter.ai/api/v1"
# O OpenRouter pede identificação do app nos cabeçalhos.
APP_URL = "https://github.com/juannobrega/lognix"
APP_TITLE = "Lognix"
TIMEOUT = 60.0
NETWORK_RETRIES = 2


class OpenRouterProvider:
    kind = "openrouter"
    name = "OpenRouter"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=(base_url or BASE_URL).rstrip("/"),
            transport=transport,
            timeout=TIMEOUT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": APP_URL,
                "X-Title": APP_TITLE,
            },
        )
        self._price_cache: dict[str, tuple[float, float]] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None,
        model: str,
        max_output_tokens: int,
    ) -> AiResult:
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_output_tokens,
            "temperature": 0,
            "usage": {"include": True},
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "insight", "strict": True, "schema": schema},
            }
        started = time.perf_counter()
        data = await self._post("/chat/completions", body)
        latency_ms = int((time.perf_counter() - started) * 1000)

        choices = data.get("choices") or []
        if not choices:
            raise AiError(f"Resposta sem conteúdo: {str(data)[:300]}")
        text = (choices[0].get("message") or {}).get("content") or ""
        if not text.strip():
            finish = choices[0].get("finish_reason")
            raise AiError(f"O modelo devolveu conteúdo vazio (finish_reason={finish}).")

        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        cost, source = await self._cost(
            data.get("model") or model, usage, prompt_tokens, completion_tokens
        )
        return AiResult(
            text=text,
            model=str(data.get("model") or model),
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            cost_usd=cost,
            cost_source=source,
            latency_ms=latency_ms,
            raw={"id": data.get("id"), "finish_reason": choices[0].get("finish_reason")},
        )

    async def test(self, model: str) -> AiResult:
        """Chamada mínima para validar chave e modelo na tela de configuração."""
        return await self.complete(
            system="Responda exatamente: ok",
            user="ok",
            schema=None,
            model=model,
            max_output_tokens=16,
        )

    async def models(self) -> list[ModelInfo]:
        data = await self._get("/models")
        out: list[ModelInfo] = []
        for item in data.get("data") or []:
            pricing = item.get("pricing") or {}
            try:
                prompt_price = float(pricing.get("prompt", 0)) * 1_000_000
                completion_price = float(pricing.get("completion", 0)) * 1_000_000
            except (TypeError, ValueError):
                prompt_price = completion_price = 0.0
            model_id = str(item.get("id") or "")
            if not model_id:
                continue
            self._price_cache[model_id] = (prompt_price, completion_price)
            out.append(
                ModelInfo(
                    id=model_id,
                    name=str(item.get("name") or model_id),
                    context_length=item.get("context_length"),
                    prompt_usd_per_mtok=prompt_price,
                    completion_usd_per_mtok=completion_price,
                )
            )
        out.sort(key=lambda m: m.id)
        return out

    # --- internos ------------------------------------------------------------

    async def _cost(
        self, model: str, usage: dict[str, Any], prompt_tokens: int, completion_tokens: int
    ) -> tuple[Decimal, CostSource]:
        # O OpenRouter devolve o custo quando usage.include está ligado.
        raw_cost = usage.get("cost")
        if raw_cost is not None:
            try:
                return Decimal(str(raw_cost)), CostSource.provider
            except (TypeError, ValueError):
                pass
        prices = self._price_cache.get(model)
        if prices is None:
            try:
                await self.models()
            except AiError:
                return Decimal(0), CostSource.unknown
            prices = self._price_cache.get(model)
        if prices is None:
            return Decimal(0), CostSource.unknown
        prompt_price, completion_price = prices
        estimated = (prompt_tokens / 1_000_000) * prompt_price + (
            completion_tokens / 1_000_000
        ) * completion_price
        return Decimal(str(round(estimated, 6))), CostSource.estimated

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, json=body)

    async def _get(self, path: str) -> dict[str, Any]:
        return await self._request("GET", path)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(NETWORK_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                last = AiError(f"Falha de rede ao falar com o OpenRouter: {exc}", retryable=True)
                if attempt < NETWORK_RETRIES:
                    continue
                raise last from exc
            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                raise RateLimitedError(
                    "O OpenRouter recusou por limite de uso.",
                    float(retry_after) if retry_after and retry_after.isdigit() else None,
                )
            if resp.status_code in (401, 403):
                raise AiError(
                    "O OpenRouter recusou a chave de API. Verifique a chave em Configurações.",
                    status=resp.status_code,
                )
            if resp.status_code == 404:
                raise AiError(
                    "Modelo não encontrado no OpenRouter. Confira o identificador.",
                    status=404,
                )
            if resp.status_code >= 500:
                last = AiError(
                    f"OpenRouter indisponível (HTTP {resp.status_code}).", retryable=True
                )
                if attempt < NETWORK_RETRIES:
                    continue
                raise last
            if resp.status_code >= 400:
                raise AiError(
                    f"OpenRouter respondeu HTTP {resp.status_code}: {resp.text[:300]}",
                    status=resp.status_code,
                )
            try:
                data = resp.json()
            except ValueError as exc:
                raise AiError("Resposta do OpenRouter não é JSON.") from exc
            if isinstance(data, dict) and data.get("error"):
                err = data["error"]
                raise AiError(f"OpenRouter: {err.get('message') or err}")
            return data if isinstance(data, dict) else {"data": data}
        raise last or AiError("Falha desconhecida ao falar com o OpenRouter.")
