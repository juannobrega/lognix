"""Barramento simples de canais para o WebSocket: executor, notificações, insights, hosts."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any

Handler = Callable[[dict[str, Any]], Any]


class Bus:
    def __init__(self) -> None:
        self._subs: dict[str, dict[int, Handler]] = {}
        self._next = 0

    def subscribe(self, channel: str, handler: Handler) -> Callable[[], None]:
        self._next += 1
        sid = self._next
        self._subs.setdefault(channel, {})[sid] = handler

        def unsubscribe() -> None:
            subs = self._subs.get(channel)
            if subs:
                subs.pop(sid, None)

        return unsubscribe

    def publish(self, channel: str, payload: dict[str, Any]) -> None:
        for handler in list(self._subs.get(channel, {}).values()):
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    task = asyncio.ensure_future(result)
                    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
            except Exception:
                with contextlib.suppress(Exception):
                    pass


_bus: Bus | None = None


def get_bus() -> Bus:
    global _bus
    if _bus is None:
        _bus = Bus()
    return _bus
