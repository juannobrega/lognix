"""TailHub: um tail do Loki por projeto, compartilhado entre espectadores."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from lognix.loki.client import LogLine, LokiClient, LokiError, selector

log = logging.getLogger(__name__)

Subscriber = Callable[[list[LogLine]], Awaitable[None]]
IDLE_CLOSE_SECONDS = 30


class _Tail:
    def __init__(self, hub: TailHub, project_id: uuid.UUID) -> None:
        self.hub = hub
        self.project_id = project_id
        self.subscribers: dict[int, Subscriber] = {}
        self.task: asyncio.Task[None] | None = None
        self.last_ts_ns: int | None = None
        self.last_error: str | None = None
        self.idle_since: float | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self._run(), name=f"tail:{self.project_id}")

    async def _run(self) -> None:
        backoff = 1.0
        while True:
            client = self.hub.client_factory()
            try:
                start = (self.last_ts_ns + 1) if self.last_ts_ns else int(time.time_ns())
                async for batch in client.tail(selector(self.project_id), start_ns=start):
                    self.last_ts_ns = max(self.last_ts_ns or 0, batch[-1].ts_ns)
                    self.last_error = None
                    backoff = 1.0
                    for sub in list(self.subscribers.values()):
                        with contextlib.suppress(Exception):
                            await sub(batch)
                # Loki fechou o tail normalmente: reabre a partir da última linha.
            except asyncio.CancelledError:
                raise
            except LokiError as exc:
                self.last_error = str(exc)
                log.warning(
                    "tail error", extra={"project_id": str(self.project_id), "error": str(exc)}
                )
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.exception("tail crashed", extra={"project_id": str(self.project_id)})
            finally:
                await client.aclose()
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    async def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self.task
            self.task = None


class TailHub:
    def __init__(self, client_factory: Callable[[], LokiClient] | None = None) -> None:
        self.client_factory = client_factory or LokiClient
        self._tails: dict[uuid.UUID, _Tail] = {}
        self._reaper: asyncio.Task[None] | None = None
        self._next_id = 0

    def start(self) -> None:
        if self._reaper is None:
            self._reaper = asyncio.create_task(self._reap_idle(), name="tailhub:reaper")

    async def stop(self) -> None:
        if self._reaper is not None:
            self._reaper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reaper
            self._reaper = None
        await asyncio.gather(*(t.stop() for t in self._tails.values()), return_exceptions=True)
        self._tails.clear()

    def subscribe(self, project_id: uuid.UUID, callback: Subscriber) -> Callable[[], None]:
        tail = self._tails.get(project_id)
        if tail is None:
            tail = _Tail(self, project_id)
            self._tails[project_id] = tail
            tail.start()
        self._next_id += 1
        sub_id = self._next_id
        tail.subscribers[sub_id] = callback
        tail.idle_since = None

        def unsubscribe() -> None:
            tail.subscribers.pop(sub_id, None)
            if not tail.subscribers:
                tail.idle_since = time.monotonic()

        return unsubscribe

    def active_projects(self) -> list[uuid.UUID]:
        return [pid for pid, t in self._tails.items() if t.subscribers]

    async def _reap_idle(self) -> None:
        while True:
            await asyncio.sleep(5)
            now = time.monotonic()
            for pid, tail in list(self._tails.items()):
                if (
                    not tail.subscribers
                    and tail.idle_since is not None
                    and now - tail.idle_since > IDLE_CLOSE_SECONDS
                ):
                    await tail.stop()
                    self._tails.pop(pid, None)


_hub: TailHub | None = None


def get_tail_hub() -> TailHub:
    global _hub
    if _hub is None:
        _hub = TailHub()
    return _hub


def set_tail_hub(hub: TailHub | None) -> None:
    global _hub
    _hub = hub
