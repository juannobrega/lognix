"""Cliente mínimo da Docker API sobre o socket do proxy somente leitura."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

SAFE_ENV_NAMES = frozenset(
    {
        "APP_VERSION",
        "APP_ENV",
        "VERSION",
        "GIT_COMMIT",
        "GIT_SHA",
        "COMMIT_SHA",
        "SOURCE_COMMIT",
        "NODE_ENV",
        "PYTHON_VERSION",
        "ENVIRONMENT",
        "ENV",
        "RELEASE",
        "SERVICE_NAME",
        "TZ",
        "LANG",
    }
)


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

    async def inspect(self, docker_id: str) -> dict[str, Any]:
        data = await self._get(f"/containers/{docker_id}/json")
        return data if isinstance(data, dict) else {}

    async def events(self, *, since: int | None = None) -> AsyncIterator[dict[str, Any]]:
        """Stream de eventos de containers. Uma requisição longa; cada linha é um JSON."""
        params: dict[str, str] = {"filters": json.dumps({"type": ["container"]})}
        if since is not None:
            params["since"] = str(since)
        try:
            async with self._client.stream(
                "GET", "/events", params=params, timeout=httpx.Timeout(10.0, read=None)
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise DockerApiError(
                        f"Docker respondeu HTTP {resp.status_code}: {body[:200]!r}",
                        resp.status_code,
                    )
                try:
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
                except asyncio.CancelledError:
                    # Não espera o fechamento gracioso do stream: derruba a conexão.
                    await asyncio.shield(_force_close(resp))
                    raise
        except httpx.HTTPError as exc:
            raise DockerApiError(f"Stream de eventos interrompido: {exc}") from exc


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


def summarize_env(inspect: dict[str, Any]) -> dict[str, Any]:
    """Variáveis de ambiente só por nome; valor apenas para a lista segura."""
    env_list: list[str] = (inspect.get("Config") or {}).get("Env") or []
    names: list[str] = []
    safe: dict[str, str] = {}
    for item in env_list:
        name, _, value = item.partition("=")
        if not name:
            continue
        names.append(name)
        if name in SAFE_ENV_NAMES:
            safe[name] = value[:200]
    return {"names": sorted(names), "safe": safe}


async def _force_close(resp: httpx.Response) -> None:
    with contextlib.suppress(Exception):
        await asyncio.wait_for(resp.aclose(), timeout=1)
