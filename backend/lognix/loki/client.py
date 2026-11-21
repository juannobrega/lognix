"""Cliente do Loki: consulta de janela e tail. ADR 001, Integração com Loki."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import websockets

from lognix.config import get_settings

log = logging.getLogger(__name__)

MAX_LIMIT = 5000


class LokiError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class LogLine:
    ts_ns: int
    line: str
    labels: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {"ts_ns": str(self.ts_ns), "line": self.line, "labels": self.labels}


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def selector(container_id: uuid.UUID, *, text: str | None = None) -> str:
    """Sempre por container_id, o uuid do Lognix. Filtro de texto é |= literal."""
    query = f'{{container_id="{container_id}"}}'
    if text:
        query += f' |= "{_escape(text)}"'
    return query


def _flatten(result: list[dict[str, Any]]) -> list[LogLine]:
    lines: list[LogLine] = []
    for stream in result:
        labels = {k: str(v) for k, v in (stream.get("stream") or {}).items()}
        for ts, line in stream.get("values") or []:
            lines.append(LogLine(int(ts), line, labels))
    lines.sort(key=lambda entry: entry.ts_ns)
    return lines


class LokiClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or get_settings().loki_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url, transport=transport, timeout=timeout
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ready(self) -> bool:
        try:
            resp = await self._client.get("/ready")
        except httpx.HTTPError:
            return False
        return resp.status_code == 200

    async def query_range(
        self,
        query: str,
        *,
        start_ns: int,
        end_ns: int,
        limit: int = 1000,
        direction: str = "backward",
    ) -> list[LogLine]:
        limit = max(1, min(limit, MAX_LIMIT))
        params = {
            "query": query,
            "start": str(start_ns),
            "end": str(end_ns),
            "limit": str(limit),
            "direction": direction,
        }
        try:
            resp = await self._client.get("/loki/api/v1/query_range", params=params)
        except httpx.HTTPError as exc:
            raise LokiError(f"Loki não respondeu: {exc}") from exc
        if resp.status_code >= 400:
            raise LokiError(
                f"Loki respondeu HTTP {resp.status_code}: {resp.text[:300]}", resp.status_code
            )
        data = resp.json()
        if data.get("status") != "success":
            raise LokiError(f"Loki: {data}")
        return _flatten(data["data"].get("result") or [])

    async def tail(
        self, query: str, *, start_ns: int | None = None, delay_for: int = 0
    ) -> AsyncIterator[list[LogLine]]:
        """Segue um seletor via WebSocket do Loki, entregando lotes de linhas."""
        params: dict[str, str] = {"query": query, "limit": "100"}
        if start_ns is not None:
            params["start"] = str(start_ns)
        if delay_for:
            params["delay_for"] = str(delay_for)
        ws_base = self.base_url.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
        url = f"{ws_base}/loki/api/v1/tail?{urlencode(params)}"
        try:
            async with websockets.connect(url, max_size=16 * 1024 * 1024) as ws:
                async for message in ws:
                    payload = json.loads(message)
                    lines = _flatten(payload.get("streams") or [])
                    if lines:
                        yield lines
        except (OSError, websockets.WebSocketException) as exc:
            raise LokiError(f"Tail do Loki interrompido: {exc}") from exc
