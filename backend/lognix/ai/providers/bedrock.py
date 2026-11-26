"""Provider do Amazon Bedrock, via API Converse.

A Converse dá uma forma única para todos os modelos do Bedrock, então não é preciso um
tradutor por fabricante. A assinatura é SigV4, feita com o `botocore` sem usar o cliente
síncrono do boto3: só o assinador, sobre o `httpx` que o resto do projeto já usa.
"""

from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from typing import Any

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from lognix.ai.models import CostSource
from lognix.ai.provider import AiError, AiResult, ModelInfo, RateLimitedError

log = logging.getLogger(__name__)

TIMEOUT = 120.0
NETWORK_RETRIES = 2


class BedrockProvider:
    kind = "bedrock"
    name = "Amazon Bedrock"

    def __init__(
        self,
        *,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        session_token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.region = region
        self._credentials = Credentials(access_key_id, secret_access_key, session_token)
        self._runtime = f"https://bedrock-runtime.{region}.amazonaws.com"
        self._control = f"https://bedrock.{region}.amazonaws.com"
        self._client = httpx.AsyncClient(transport=transport, timeout=TIMEOUT)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _sign(self, method: str, url: str, body: str, service: str = "bedrock") -> dict[str, str]:
        request = AWSRequest(
            method=method, url=url, data=body or None, headers={"Content-Type": "application/json"}
        )
        SigV4Auth(self._credentials, service, self.region).add_auth(request)
        return dict(request.headers)

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None,
        model: str,
        max_output_tokens: int,
    ) -> AiResult:
        prompt = user
        if schema is not None:
            # A Converse não tem response_format universal: o esquema vai no prompt, e o
            # validador do Lognix é quem garante o formato de qualquer jeito.
            prompt = (
                f"{user}\n\nResponda apenas com um objeto JSON que satisfaça este JSON Schema, "
                f"sem texto fora dele:\n{json.dumps(schema, ensure_ascii=False)}"
            )
        body = json.dumps(
            {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "system": [{"text": system}],
                # Sem `temperature`: o Bedrock serve os mesmos modelos da Anthropic, que a
                # descontinuaram e devolvem 400 quando ela aparece.
                "inferenceConfig": {"maxTokens": max_output_tokens},
            }
        )
        url = f"{self._runtime}/model/{model}/converse"
        started = time.perf_counter()
        data = await self._request("POST", url, body, service="bedrock")
        latency_ms = int((time.perf_counter() - started) * 1000)

        blocks = ((data.get("output") or {}).get("message") or {}).get("content") or []
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
        if not text.strip():
            raise AiError(
                f"O modelo devolveu conteúdo vazio (stopReason={data.get('stopReason')})."
            )
        usage = data.get("usage") or {}
        return AiResult(
            text=text,
            model=model,
            input_tokens=int(usage.get("inputTokens") or 0),
            output_tokens=int(usage.get("outputTokens") or 0),
            # O Bedrock não devolve custo: quem calcula é o chamador, pelo preço do modelo.
            cost_usd=Decimal(0),
            cost_source=CostSource.unknown,
            latency_ms=latency_ms,
            raw={"stopReason": data.get("stopReason"), "metrics": data.get("metrics")},
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
        """Modelos base disponíveis na conta e na região, que aceitam texto nas duas pontas."""
        data = await self._request(
            "GET", f"{self._control}/foundation-models", "", service="bedrock"
        )
        out: list[ModelInfo] = []
        for item in data.get("modelSummaries") or []:
            model_id = str(item.get("modelId") or "")
            if not model_id:
                continue
            inputs = item.get("inputModalities") or []
            outputs = item.get("outputModalities") or []
            if "TEXT" not in inputs or "TEXT" not in outputs:
                continue
            provider = item.get("providerName") or ""
            label = item.get("modelName") or model_id
            out.append(ModelInfo(id=model_id, name=f"{provider} {label}".strip()))
        out.sort(key=lambda m: m.id)
        return out

    async def _request(self, method: str, url: str, body: str, *, service: str) -> dict[str, Any]:
        last: AiError | None = None
        for attempt in range(NETWORK_RETRIES + 1):
            headers = self._sign(method, url, body, service)
            try:
                resp = await self._client.request(
                    method, url, content=body.encode() if body else None, headers=headers
                )
            except httpx.HTTPError as exc:
                last = AiError(f"Falha de rede ao falar com o Bedrock: {exc}", retryable=True)
                if attempt < NETWORK_RETRIES:
                    continue
                raise last from exc

            if resp.status_code == 429:
                raise RateLimitedError("O Bedrock recusou por limite de uso da conta.")
            if resp.status_code in (401, 403):
                raise AiError(
                    "O Bedrock recusou as credenciais. Confira as chaves e se o usuário IAM tem "
                    "permissão de bedrock:InvokeModel.",
                    status=resp.status_code,
                )
            if resp.status_code == 404:
                raise AiError(
                    "Modelo não encontrado nesta região. Confira o identificador e se o acesso "
                    "ao modelo está habilitado na conta.",
                    status=404,
                )
            if resp.status_code in (408, 503) or resp.status_code >= 500:
                last = AiError(f"Bedrock indisponível (HTTP {resp.status_code}).", retryable=True)
                if attempt < NETWORK_RETRIES:
                    continue
                raise last
            if resp.status_code >= 400:
                detail = ""
                try:
                    payload = resp.json()
                    detail = payload.get("message") or payload.get("Message") or resp.text[:200]
                except ValueError:
                    detail = resp.text[:200]
                raise AiError(
                    f"Bedrock respondeu HTTP {resp.status_code}: {detail}", status=resp.status_code
                )
            try:
                data = resp.json()
            except ValueError as exc:
                raise AiError("Resposta do Bedrock não é JSON.") from exc
            return data if isinstance(data, dict) else {"data": data}
        raise last or AiError("Falha desconhecida ao falar com o Bedrock.")
