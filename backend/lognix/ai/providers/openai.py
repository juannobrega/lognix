"""Provider da OpenAI. A API de chat é a mesma forma que o OpenRouter expõe, mas o catálogo
de modelos não traz preço, então os valores vêm da configuração de cada modelo."""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

import httpx

from lognix.ai.models import CostSource
from lognix.ai.provider import AiError, AiResult, ModelInfo, RateLimitedError

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
TIMEOUT = 60.0
NETWORK_RETRIES = 2


class OpenAiProvider:
    kind = "openai"
    name = "OpenAI"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        organization: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        kind: str = "openai",
        name: str = "OpenAI",
    ) -> None:
        # Groq, Mistral, DeepSeek e companhia usam esta mesma classe: o que muda é a URL e o nome
        # que aparece nos erros. Dizer "a OpenAI recusou a chave" quando quem recusou foi a Groq
        # manda o usuário conferir a credencial errada.
        self.kind = kind
        self.name = name
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        if organization:
            headers["OpenAI-Organization"] = organization
        self._client = httpx.AsyncClient(
            base_url=(base_url or DEFAULT_BASE_URL).rstrip("/"),
            transport=transport,
            timeout=TIMEOUT,
            headers=headers,
        )

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
            "max_completion_tokens": max_output_tokens,
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "insight", "strict": True, "schema": schema},
            }
        started = time.perf_counter()
        data = await self._request("POST", "/chat/completions", json=body)
        latency_ms = int((time.perf_counter() - started) * 1000)

        choices = data.get("choices") or []
        if not choices:
            raise AiError(f"Resposta sem conteúdo: {str(data)[:300]}")
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        if not str(text).strip():
            finish = choices[0].get("finish_reason")
            raise AiError(f"O modelo devolveu conteúdo vazio (finish_reason={finish}).")
        usage = data.get("usage") or {}
        return AiResult(
            text=str(text),
            model=str(data.get("model") or model),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            # A OpenAI não devolve custo. Quem calcula é o chamador, com o preço do modelo.
            cost_usd=Decimal(0),
            cost_source=CostSource.unknown,
            latency_ms=latency_ms,
            raw={"id": data.get("id"), "finish_reason": choices[0].get("finish_reason")},
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
        data = await self._request("GET", "/models")
        out = [
            ModelInfo(id=str(item["id"]), name=str(item["id"]))
            for item in (data.get("data") or [])
            if item.get("id")
        ]
        out.sort(key=lambda m: m.id)
        return out

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last: AiError | None = None
        for attempt in range(NETWORK_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                last = AiError(f"Falha de rede ao falar com {self.name}: {exc}", retryable=True)
                if attempt < NETWORK_RETRIES:
                    continue
                raise last from exc
            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                raise RateLimitedError(
                    f"{self.name} recusou por limite de uso.",
                    float(retry_after) if retry_after and retry_after.isdigit() else None,
                )
            if resp.status_code in (401, 403):
                raise AiError(
                    f"{self.name} recusou a chave de API. Verifique a credencial.",
                    status=resp.status_code,
                )
            if resp.status_code == 404:
                raise AiError(
                    f"Modelo não encontrado em {self.name}. Confira o identificador.", status=404
                )
            if resp.status_code >= 500:
                last = AiError(
                    f"{self.name} indisponível (HTTP {resp.status_code}).", retryable=True
                )
                if attempt < NETWORK_RETRIES:
                    continue
                raise last
            if resp.status_code >= 400:
                detail = ""
                try:
                    detail = (resp.json().get("error") or {}).get("message") or ""
                except ValueError:
                    detail = resp.text[:200]
                raise AiError(
                    f"{self.name} respondeu HTTP {resp.status_code}: {detail}",
                    status=resp.status_code,
                )
            try:
                data = resp.json()
            except ValueError as exc:
                raise AiError(f"Resposta de {self.name} não é JSON.") from exc
            return data if isinstance(data, dict) else {"data": data}
        raise last or AiError(f"Falha desconhecida ao falar com {self.name}.")
