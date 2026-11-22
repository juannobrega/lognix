"""Um loop de análise por container monitorado, com 30 s entre o fim de um ciclo e o próximo."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from lognix.analysis.cycle import run_cycle
from lognix.analysis.executor import get_executor
from lognix.analysis.models import AnalysisRun
from lognix.analysis.patterns import drop_miner
from lognix.containers.models import Container, ContainerState
from lognix.db import get_sessionmaker
from lognix.hosts.models import HostStatus
from lognix.loki.client import LokiClient

log = logging.getLogger(__name__)

CYCLE_PAUSE = 30
RECONCILE_LOOPS = 15
MAX_FIRST_WINDOW = timedelta(minutes=15)


class ContainerLoop:
    def __init__(self, container_id: uuid.UUID, manager: AnalysisManager) -> None:
        self.container_id = container_id
        self.manager = manager
        self.task: asyncio.Task[None] | None = None
        self.last_window_end: datetime | None = None
        self.cycles = 0
        self.last_error: str | None = None
        self._lock = asyncio.Lock()
        self._inflight: asyncio.Future[None] | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self._run(), name=f"analysis:{self.container_id}")

    async def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(self.task, timeout=5)
            self.task = None
        if self._inflight is not None and not self._inflight.done():
            # O ciclo é blindado contra cancelamento: espera terminar para não deixar
            # transação aberta no pool.
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(asyncio.shield(self._inflight), timeout=30)

    async def _run(self) -> None:
        await self._load_state()
        while True:
            try:
                self._inflight = asyncio.ensure_future(self.cycle_once())
                await asyncio.shield(self._inflight)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.exception(
                    "analysis cycle crashed", extra={"container_id": str(self.container_id)}
                )
            await asyncio.sleep(self.manager.pause_seconds)

    async def _load_state(self) -> None:
        async with get_sessionmaker()() as db:
            last = (
                await db.execute(
                    select(AnalysisRun.window_end)
                    .where(
                        AnalysisRun.container_id == self.container_id, AnalysisRun.manual.is_(False)
                    )
                    .order_by(AnalysisRun.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            self.last_window_end = last

    async def cycle_once(self) -> None:
        async with self._lock:
            async with get_sessionmaker()() as db:
                container = await db.get(Container, self.container_id)
                if (
                    container is None
                    or not container.monitored
                    or container.state == ContainerState.removed
                    or container.host.status == HostStatus.removed
                ):
                    return
                now = datetime.now(UTC)
                start = self.last_window_end or container.monitored_since or now
                if now - start > MAX_FIRST_WINDOW and self.last_window_end is None:
                    start = now - MAX_FIRST_WINDOW
                if now <= start:
                    return
                key = get_executor().start(
                    container.id, container.name, container.host.name, "cycle"
                )
                client = self.manager.client_factory()
                try:
                    result = await run_cycle(
                        db,
                        client,
                        container,
                        window_start=start,
                        window_end=now,
                        on_phase=lambda p, **d: get_executor().phase(key, p, **d),
                    )
                finally:
                    await client.aclose()
                    get_executor().finish(key)
                if result.run.status.value != "failed":
                    # Falha no Loki não avança a janela: nenhuma linha é pulada.
                    self.last_window_end = now
                self.cycles += 1
                self.last_error = result.run.error


class AnalysisManager:
    def __init__(self, client_factory=None, pause_seconds: int = CYCLE_PAUSE) -> None:  # type: ignore[no-untyped-def]
        self.client_factory = client_factory or LokiClient
        self.pause_seconds = pause_seconds
        self._loops: dict[uuid.UUID, ContainerLoop] = {}
        self._reconciler: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.reconcile()
        self._reconciler = asyncio.create_task(self._reconcile_loop(), name="analysis:reconcile")

    async def stop(self) -> None:
        if self._reconciler is not None:
            self._reconciler.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconciler
            self._reconciler = None
        await asyncio.gather(*(lp.stop() for lp in self._loops.values()), return_exceptions=True)
        self._loops.clear()

    async def _reconcile_loop(self) -> None:
        while True:
            await asyncio.sleep(RECONCILE_LOOPS)
            with contextlib.suppress(Exception):
                await self.reconcile()

    async def reconcile(self) -> None:
        """Garante um loop por container monitorado e nenhum para os demais."""
        async with get_sessionmaker()() as db:
            ids = set(
                (
                    await db.execute(
                        select(Container.id).where(
                            Container.monitored.is_(True), Container.state != ContainerState.removed
                        )
                    )
                ).scalars()
            )
        for cid in ids - self._loops.keys():
            loop = self._loops[cid] = ContainerLoop(cid, self)
            loop.start()
        for cid in list(self._loops.keys() - ids):
            await self._loops.pop(cid).stop()
            drop_miner(cid)

    def get(self, container_id: uuid.UUID) -> ContainerLoop | None:
        return self._loops.get(container_id)

    def status(self) -> list[dict[str, object]]:
        return [
            {
                "container_id": str(cid),
                "cycles": lp.cycles,
                "last_window_end": lp.last_window_end.isoformat() if lp.last_window_end else None,
                "last_error": lp.last_error,
            }
            for cid, lp in self._loops.items()
        ]


_manager: AnalysisManager | None = None


def get_analysis_manager() -> AnalysisManager:
    global _manager
    if _manager is None:
        _manager = AnalysisManager()
    return _manager


def set_analysis_manager(manager: AnalysisManager | None) -> None:
    global _manager
    _manager = manager
