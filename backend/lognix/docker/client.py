"""Cliente mínimo da Docker API sobre o socket do proxy somente leitura."""

from __future__ import annotations

from typing import Any

import httpx


class DockerApiError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class DockerClient:
    def __init__(self, socket_path: str, *, timeout: float = 10.0) -> None:
        self._client = httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(uds=socket_path),
            base_url="http://docker",
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, **params: Any) -> Any:
        try:
            resp = await self._client.get(path, params=params or None)
        except httpx.HTTPError as exc:
            raise DockerApiError(f"Docker não respondeu: {exc}") from exc
        if resp.status_code >= 400:
            raise DockerApiError(
                f"Docker respondeu HTTP {resp.status_code}: {resp.text[:200]}", resp.status_code
            )
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.text

    async def ping(self) -> bool:
        return bool((await self._get("/_ping")) == "OK")

    async def version(self) -> dict[str, Any]:
        data = await self._get("/version")
        return data if isinstance(data, dict) else {}

    async def containers(self, *, all: bool = True) -> list[dict[str, Any]]:
        data = await self._get("/containers/json", all="true" if all else "false")
        return data if isinstance(data, list) else []


def summarize_container(raw: dict[str, Any]) -> dict[str, Any]:
    labels: dict[str, str] = raw.get("Labels") or {}
    names = raw.get("Names") or []
    name = names[0].lstrip("/") if names else raw.get("Id", "")[:12]
    return {
        "docker_id": raw.get("Id", ""),
        "name": name,
        "image": raw.get("Image", ""),
        "state": raw.get("State", ""),
        "status": raw.get("Status", ""),
        "compose_project": labels.get("com.docker.compose.project"),
        "compose_service": labels.get("com.docker.compose.service"),
        "labels": labels,
    }
