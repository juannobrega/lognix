"""Provider da Anthropic. Protocolo próprio: /v1/messages, não a API de chat da OpenAI.

Três diferenças que obrigam uma implementação separada: a credencial vai no cabeçalho `x-api-key`
e não em `Authorization`, a versão da API é obrigatória em `anthropic-version`, e o `system` é um
campo de primeira classe no corpo em vez de uma mensagem com papel `system`.

Como não existe `response_format`, o esquema vai no prompt — mesma estratégia do Bedrock.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

import httpx

from lognix.ai.models import CostSource
from lognix.ai.provider import AiError, AiResult, ModelInfo, RateLimitedError

log = logging.getLogger(__name__)

BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"
TIMEOUT = 60.0
NETWORK_RETRIES = 2


class AnthropicProvider:
    kind = "anthropic"
    name = "Anthropic"

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
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
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
        instructions = system
        if schema is not None:
            instructions = (
                f"{system}\n\nResponda com um único objeto JSON válido, sem cercas de código e "
                f"sem texto em volta, exatamente neste esquema:\n{schema}"
            )
        # Sem `temperature`: os modelos novos da Anthropic a descontinuaram e respondem HTTP 400
        # quando ela vem no corpo. O padrão do serviço já é determinístico o bastante para o que
        # pedimos — JSON num esquema fechado —, e mandar o parâmetro só para "garantir" trocaria
        # um ganho nenhum por uma recusa na cara do usuário.
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_output_tokens,
            "system": instructions,
            "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
        }
        started = time.perf_counter()
        data = await self._request("POST", "/v1/messages", json=body)
        latency_ms = int((time.perf_counter() - started) * 1000)

        blocks = data.get("content") or []
        text = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
        if not text.strip():
            raise AiError(f"A Anthropic devolveu conteúdo vazio (stop={data.get('stop_reason')}).")
        usage = data.get("usage") or {}
        return AiResult(
            text=text,
            model=str(data.get("model") or model),
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            # A Anthropic não devolve custo: quem calcula é o chamador, pelo preço do modelo.
            cost_usd=Decimal(0),
            cost_source=CostSource.unknown,
            latency_ms=latency_ms,
            raw={"id": data.get("id"), "stop_reason": data.get("stop_reason")},
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
        data = await self._request("GET", "/v1/models", params={"limit": 1000})
        out = [
            ModelInfo(id=str(i["id"]), name=str(i.get("display_name") or i["id"]))
            for i in (data.get("data") or [])
            if i.get("id")
        ]
        out.sort(key=lambda m: m.id)
        return out

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last: AiError | None = None
        for attempt in range(NETWORK_RETRIES + 1):
            try:
                resp = await self._client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                last = AiError(f"Falha de rede ao falar com a Anthropic: {exc}", retryable=True)
                if attempt < NETWORK_RETRIES:
                    continue
                raise last from exc
            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                raise RateLimitedError(
                    "A Anthropic recusou por limite de uso.",
                    float(retry_after) if retry_after and retry_after.isdigit() else None,
                )
            if resp.status_code in (401, 403):
                raise AiError("A Anthropic recusou a chave de API.", status=resp.status_code)
            if resp.status_code == 404:
                raise AiError(
                    "Modelo não encontrado na Anthropic. Confira o identificador.", status=404
                )
            if resp.status_code >= 500:
                last = AiError(f"Anthropic indisponível (HTTP {resp.status_code}).", retryable=True)
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
                    f"Anthropic respondeu HTTP {resp.status_code}: {detail}",
                    status=resp.status_code,
                )
            try:
                data = resp.json()
            except ValueError as exc:
                raise AiError("Resposta da Anthropic não é JSON.") from exc
            return data if isinstance(data, dict) else {"data": data}
        raise last or AiError("Falha desconhecida ao falar com a Anthropic.")
