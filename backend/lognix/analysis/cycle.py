"""Um ciclo de análise: janela do Loki → Drain → classificação → estatísticas → triggers."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.ai.service import analyze_trigger
from lognix.analysis import triggers as trig
from lognix.analysis.classifier import classify
from lognix.analysis.models import (
    AnalysisRun,
    LogLevel,
    Pattern,
    RunStatus,
    TriggerFired,
    TriggerType,
)
from lognix.analysis.patterns import miner_for
from lognix.containers.models import Container
from lognix.events.models import DockerEvent
from lognix.loki.client import LogLine, LokiClient, LokiError, selector
from lognix.metrics import cycle_duration, cycle_lines, cycles_total, triggers_total

log = logging.getLogger(__name__)

PAGE = 5000
MAX_LINES_PER_CYCLE = 50_000
BASELINE_RUNS = 30
# Drain e regex são trabalho de CPU em Python puro: sem ceder o loop, um ciclo longo
# segura a API inteira. Medido na 0.7.0. Ceder a cada bloco mantém a API responsiva.
YIELD_EVERY = 250

# Um ciclo por container de cada vez. A análise manual e o ciclo automático podem coincidir;
# sem isso processam janelas sobrepostas e disputam a criação dos mesmos padrões.
_cycle_locks: dict[uuid.UUID, asyncio.Lock] = {}


def cycle_lock(container_id: uuid.UUID) -> asyncio.Lock:
    lock = _cycle_locks.get(container_id)
    if lock is None:
        lock = _cycle_locks[container_id] = asyncio.Lock()
    return lock


def drop_cycle_lock(container_id: uuid.UUID) -> None:
    _cycle_locks.pop(container_id, None)


@dataclass
class CycleResult:
    run: AnalysisRun
    fired: list[TriggerFired]
    insights: list[Any] = field(default_factory=list)
    ai_error: str | None = None


async def fetch_window(
    client: LokiClient, container_id: uuid.UUID, start: datetime, end: datetime
) -> tuple[list[LogLine], bool]:
    """Pagina a janela em blocos de 5 000 até o teto de 50 000 linhas."""
    lines: list[LogLine] = []
    cursor_ns = int(start.timestamp() * 1e9)
    end_ns = int(end.timestamp() * 1e9)
    query = selector(container_id)
    truncated = False
    while True:
        batch = await client.query_range(
            query, start_ns=cursor_ns, end_ns=end_ns, limit=PAGE, direction="forward"
        )
        lines.extend(batch)
        if len(batch) < PAGE:
            break
        cursor_ns = batch[-1].ts_ns + 1
        if len(lines) >= MAX_LINES_PER_CYCLE:
            truncated = True
            break
    return lines, truncated


async def _patterns_by_template(db: AsyncSession, container_id: uuid.UUID) -> dict[str, Pattern]:
    rows = (await db.execute(select(Pattern).where(Pattern.container_id == container_id))).scalars()
    return {p.template: p for p in rows}


async def run_cycle(
    db: AsyncSession,
    client: LokiClient,
    container: Container,
    *,
    window_start: datetime,
    window_end: datetime,
    manual: bool = False,
    fired_by: uuid.UUID | None = None,
    on_phase: Callable[..., Any] | None = None,
) -> CycleResult:
    t0 = time.monotonic()
    now = datetime.now(UTC)

    def phase(name: str, **detail: Any) -> None:
        if on_phase is not None:
            on_phase(name, **detail)

    def observe_phase(name: str, started: float) -> None:
        cycle_duration.labels(name).observe(time.monotonic() - started)

    phase("consultando")
    t_query = time.monotonic()
    try:
        lines, truncated = await fetch_window(client, container.id, window_start, window_end)
    except LokiError as exc:
        run = AnalysisRun(
            container_id=container.id,
            window_start=window_start,
            window_end=window_end,
            status=RunStatus.failed,
            error=str(exc)[:1000],
            manual=manual,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
        db.add(run)
        await db.commit()
        cycles_total.labels("failed").inc()
        return CycleResult(run, [])

    observe_phase("loki", t_query)
    cycle_lines.observe(len(lines))
    phase("agrupando", lines=len(lines))
    t_drain = time.monotonic()
    miner = miner_for(container.id)
    existing = await _patterns_by_template(db, container.id)
    if not existing and miner.cluster_count == 0:
        pass
    elif miner.cluster_count == 0 and existing:
        miner.seed([p.sample for p in existing.values() if p.sample])

    # Agrupa por cluster do Drain; o template de um cluster evolui conforme novas linhas chegam,
    # então só se resolve o texto final depois de minerar a janela inteira.
    cluster_counts: dict[int, int] = {}
    cluster_levels: dict[int, LogLevel] = {}
    cluster_samples: dict[int, str] = {}
    created_clusters: set[int] = set()
    errors = warns = 0
    error_samples: list[dict[str, object]] = []
    for index, ln in enumerate(lines):
        if index and index % YIELD_EVERY == 0:
            await asyncio.sleep(0)
        level = classify(ln.line)
        if level == LogLevel.error:
            errors += 1
            if len(error_samples) < trig.MAX_SAMPLE_LINES:
                error_samples.append({"ts_ns": str(ln.ts_ns), "line": ln.line[:500]})
        elif level == LogLevel.warn:
            warns += 1
        mined = miner.add(ln.line)
        cid = mined.cluster_id
        cluster_counts[cid] = cluster_counts.get(cid, 0) + 1
        if cid not in cluster_samples:
            cluster_samples[cid] = ln.line[:500]
            cluster_levels[cid] = level
        elif level == LogLevel.error and cluster_levels.get(cid) != LogLevel.error:
            cluster_levels[cid] = level
        if mined.is_new:
            created_clusters.add(cid)
    counts: dict[str, int] = {}
    levels: dict[str, LogLevel] = {}
    samples: dict[str, str] = {}
    new_templates: list[str] = []
    for cid, count in cluster_counts.items():
        template = miner.template_of(cid) or cluster_samples[cid]
        counts[template] = counts.get(template, 0) + count
        samples.setdefault(template, cluster_samples[cid])
        if levels.get(template) != LogLevel.error:
            levels[template] = cluster_levels[cid]
        if cid in created_clusters and template not in existing:
            new_templates.append(template)

    observe_phase("drain", t_drain)
    phase("classificando", errors=errors)
    t_persist = time.monotonic()
    new_patterns = 0
    to_insert: list[dict[str, Any]] = []
    for template, count in counts.items():
        pattern = existing.get(template)
        if pattern is None:
            to_insert.append(
                {
                    "id": uuid.uuid4(),
                    "container_id": container.id,
                    "template": template,
                    "level": levels.get(template, LogLevel.unknown),
                    "count_total": count,
                    "sample": samples.get(template, ""),
                    "first_seen_at": now,
                    "last_seen_at": now,
                }
            )
            new_patterns += 1
            continue
        pattern.count_total += count
        pattern.last_seen_at = now
        if levels.get(template) == LogLevel.error and pattern.level != LogLevel.error:
            pattern.level = LogLevel.error
    if to_insert:
        # Upsert: se outra transação criou o mesmo padrão entre a leitura e a escrita, soma
        # a contagem em vez de estourar a unicidade (container_id, template).
        stmt = pg_insert(Pattern).values(to_insert)
        await db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_patterns_container_template",
                set_={
                    "count_total": Pattern.count_total + stmt.excluded.count_total,
                    "last_seen_at": stmt.excluded.last_seen_at,
                },
            )
        )

    seconds = max((window_end - window_start).total_seconds(), 1.0)
    stats = trig.WindowStats(
        lines=len(lines),
        errors=errors,
        warns=warns,
        new_patterns=new_patterns,
        seconds=seconds,
        error_samples=error_samples,
        new_pattern_templates=[t for t in new_templates if t in existing][:10],
    )
    run = AnalysisRun(
        container_id=container.id,
        window_start=window_start,
        window_end=window_end,
        lines_count=len(lines),
        error_lines_count=errors,
        warn_lines_count=warns,
        new_patterns_count=new_patterns,
        truncated=truncated,
        manual=manual,
        status=RunStatus.ok,
    )
    db.add(run)
    await db.flush()

    observe_phase("persist", t_persist)
    phase("avaliando triggers")
    t_trig = time.monotonic()
    events = list(
        (
            await db.execute(
                select(DockerEvent).where(
                    DockerEvent.container_id == container.id,
                    DockerEvent.occurred_at >= window_start - timedelta(minutes=5),
                    DockerEvent.occurred_at <= window_end,
                )
            )
        ).scalars()
    )
    baseline = list(
        (
            await db.execute(
                select(AnalysisRun)
                .where(AnalysisRun.container_id == container.id, AnalysisRun.id != run.id)
                .order_by(AnalysisRun.id.desc())
                .limit(BASELINE_RUNS)
            )
        ).scalars()
    )
    fired_list: list[trig.Fired] = []
    if manual:
        fired_list.append(
            trig.Fired(
                TriggerType.manual,
                {"error_lines": errors, "lines": len(lines)},
                "análise manual",
            )
        )
    else:
        for f in (
            trig.evaluate_error(stats),
            trig.evaluate_docker_events(events),
            trig.evaluate_anomaly(stats, baseline),
        ):
            if f is not None:
                fired_list.append(f)

    fired: list[TriggerFired] = []
    for f in fired_list:
        tf = TriggerFired(
            analysis_run_id=run.id,
            container_id=container.id,
            type=f.type,
            reason=f.reason,
            fired_by=fired_by,
            fired_at=now,
            window_start=window_start,
            window_end=window_end,
            sample_lines=error_samples,
            note=f.note[:255],
        )
        db.add(tf)
        fired.append(tf)

    observe_phase("triggers", t_trig)
    await db.commit()
    cycles_total.labels("truncated" if truncated else "ok").inc()
    for tf in fired:
        triggers_total.labels(tf.type.value).inc()

    # IA: um insight por trigger, quando a IA estiver ativa. O ciclo espera a resposta;
    # é o que garante no máximo uma chamada por ciclo por container. ADR 005.
    insights: list[Any] = []
    ai_error: str | None = None
    if fired:
        phase("aguardando IA")
        t_ai = time.monotonic()
        level_by_index = {i: classify(ln.line) for i, ln in enumerate(lines)}
        for tf in fired:
            outcome = await analyze_trigger(
                db,
                container=container,
                trigger=tf,
                lines=lines,
                levels=level_by_index,
                new_pattern_templates=stats.new_pattern_templates,
                state=None,
            )
            if outcome.insight is not None:
                insights.append(outcome.insight)
            if outcome.error:
                ai_error = outcome.error
        if insights or ai_error:
            run.ai_called = True
            run.ai_duration_ms = int((time.monotonic() - t_ai) * 1000)
            observe_phase("ai", t_ai)

    run.duration_ms = int((time.monotonic() - t0) * 1000)
    await db.commit()
    for tf in fired:
        await db.refresh(tf)
    await db.refresh(run)
    return CycleResult(run, fired, insights, ai_error)
