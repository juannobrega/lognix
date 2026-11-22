"""Executor: estado em memória das análises em andamento, publicado por WebSocket."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from lognix.realtime.bus import get_bus


@dataclass
class Running:
    container_id: str
    container_name: str
    host_name: str
    trigger: str  # "cycle" | "manual"
    phase: str
    started_at: float
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["elapsed_ms"] = int((time.monotonic() - self.started_at) * 1000)
        d.pop("started_at")
        return d


class Executor:
    def __init__(self) -> None:
        self._running: dict[str, Running] = {}

    def start(
        self, container_id: uuid.UUID, container_name: str, host_name: str, trigger: str
    ) -> str:
        key = f"{container_id}:{trigger}:{uuid.uuid4().hex[:6]}"
        self._running[key] = Running(
            str(container_id), container_name, host_name, trigger, "consultando", time.monotonic()
        )
        self._publish()
        return key

    def phase(self, key: str, phase: str, **detail: Any) -> None:
        run = self._running.get(key)
        if run is None:
            return
        run.phase = phase
        run.detail.update(detail)
        self._publish()

    def finish(self, key: str) -> None:
        if self._running.pop(key, None) is not None:
            self._publish()

    def snapshot(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._running.values()]

    def _publish(self) -> None:
        get_bus().publish("executor", {"type": "executor", "running": self.snapshot()})


_executor: Executor | None = None


def get_executor() -> Executor:
    global _executor
    if _executor is None:
        _executor = Executor()
    return _executor
