"""Endpoint WebSocket /ws. Autenticação pelo access token na query. Canais por mensagem."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from lognix.auth import service as auth_service
from lognix.containers.models import Container
from lognix.db import get_sessionmaker
from lognix.loki.client import LogLine
from lognix.realtime.bus import get_bus
from lognix.realtime.hub import get_tail_hub

log = logging.getLogger(__name__)
router = APIRouter()


async def _authenticate(ws: WebSocket) -> bool:
    token = ws.query_params.get("token")
    if not token:
        return False
    async with get_sessionmaker()() as db:
        return await auth_service.resolve_access_token(db, token) is not None


async def _project_exists(project_id: uuid.UUID) -> bool:
    async with get_sessionmaker()() as db:
        return await db.get(Container, project_id) is not None


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    if not await _authenticate(ws):
        await ws.close(code=4401, reason="unauthorized")
        return
    await ws.accept()
    unsubscribers: dict[str, Callable[[], None]] = {}
    send_lock = asyncio.Lock()

    async def send(payload: dict[str, Any]) -> None:
        async with send_lock:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json(payload)

    async def handle_subscribe(channel: str) -> None:
        if channel in unsubscribers:
            return
        if channel.startswith("logs:"):
            try:
                project_id = uuid.UUID(channel.split(":", 1)[1])
            except ValueError:
                await send({"type": "error", "channel": channel, "message": "canal inválido"})
                return
            if not await _project_exists(project_id):
                await send(
                    {"type": "error", "channel": channel, "message": "projeto não encontrado"}
                )
                return

            async def on_lines(lines: list[LogLine]) -> None:
                await send(
                    {"type": "lines", "channel": channel, "lines": [ln.to_dict() for ln in lines]}
                )

            unsubscribers[channel] = get_tail_hub().subscribe(project_id, on_lines)
            await send({"type": "subscribed", "channel": channel})
        elif channel in ("executor", "notifications", "insights", "hosts"):

            async def on_event(payload: dict[str, Any], _channel: str = channel) -> None:
                await send({**payload, "channel": _channel})

            unsubscribers[channel] = get_bus().subscribe(channel, on_event)
            await send({"type": "subscribed", "channel": channel})
            if channel == "executor":
                from lognix.analysis.executor import get_executor

                await send(
                    {"type": "executor", "channel": channel, "running": get_executor().snapshot()}
                )
        else:
            await send({"type": "error", "channel": channel, "message": "canal desconhecido"})

    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            channel = str(msg.get("channel", ""))
            if kind == "subscribe":
                await handle_subscribe(channel)
            elif kind == "unsubscribe":
                unsub = unsubscribers.pop(channel, None)
                if unsub:
                    unsub()
                await send({"type": "unsubscribed", "channel": channel})
            elif kind == "ping":
                await send({"type": "pong"})
            else:
                await send({"type": "error", "message": "mensagem desconhecida"})
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("websocket error")
    finally:
        for unsub in unsubscribers.values():
            with contextlib.suppress(Exception):
                unsub()
