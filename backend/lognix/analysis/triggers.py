"""Avaliação de triggers sobre uma janela analisada. Determinístico, sem IA."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from lognix.analysis.models import AnalysisRun, TriggerType
from lognix.events.models import DockerEvent, DockerEventType

RESTART_LOOP_COUNT = 3
RESTART_LOOP_WINDOW = timedelta(minutes=5)
ANOMALY_MIN_BASELINE = 10
MAX_SAMPLE_LINES = 20


@dataclass
class WindowStats:
    lines: int
    errors: int
    warns: int
    new_patterns: int
    seconds: float
    error_samples: list[dict[str, Any]] = field(default_factory=list)
    new_pattern_templates: list[str] = field(default_factory=list)


@dataclass
class Fired:
    type: TriggerType
    reason: dict[str, Any]
    note: str


def evaluate_error(stats: WindowStats) -> Fired | None:
    if stats.errors <= 0:
        return None
    return Fired(
        TriggerType.error,
        {"error_lines": stats.errors, "lines": stats.lines},
        f"{stats.errors} linha(s) de erro na janela",
    )


def evaluate_docker_events(events: list[DockerEvent]) -> Fired | None:
    """Eventos críticos na janela: die com exit code != 0, oom, unhealthy, restart em loop."""
    critical: list[dict[str, Any]] = []
    restarts: list[DockerEvent] = []
    for ev in events:
        if ev.type == DockerEventType.die and (ev.exit_code or 0) != 0:
            critical.append(
                {"type": "die", "exit_code": ev.exit_code, "at": ev.occurred_at.isoformat()}
            )
        elif ev.type == DockerEventType.oom:
            critical.append({"type": "oom", "at": ev.occurred_at.isoformat()})
        elif ev.type == DockerEventType.health_status and "unhealthy" in str(
            ev.attributes.get("action", "")
        ):
            critical.append({"type": "unhealthy", "at": ev.occurred_at.isoformat()})
        elif ev.type == DockerEventType.restart:
            restarts.append(ev)
    restarts.sort(key=lambda e: e.occurred_at)
    for i in range(len(restarts)):
        window = [
            e
            for e in restarts[i:]
            if e.occurred_at - restarts[i].occurred_at <= RESTART_LOOP_WINDOW
        ]
        if len(window) >= RESTART_LOOP_COUNT:
            critical.append(
                {
                    "type": "restart_loop",
                    "count": len(window),
                    "since": restarts[i].occurred_at.isoformat(),
                }
            )
            break
    if not critical:
        return None
    kinds = sorted({c["type"] for c in critical})
    return Fired(
        TriggerType.docker_event, {"events": critical}, "evento Docker crítico: " + ", ".join(kinds)
    )


def evaluate_anomaly(stats: WindowStats, baseline: list[AnalysisRun]) -> Fired | None:
    """Desvio estatístico frente aos ciclos anteriores do mesmo container."""
    runs = [r for r in baseline if r.status.value == "ok" and not r.manual]
    if len(runs) < ANOMALY_MIN_BASELINE or stats.seconds <= 0:
        return None

    def rate(r: AnalysisRun) -> float:
        secs = max((r.window_end - r.window_start).total_seconds(), 1.0)
        return r.lines_count / secs

    rates = [rate(r) for r in runs]
    mean = statistics.fmean(rates)
    std = statistics.pstdev(rates)
    current = stats.lines / stats.seconds
    findings: list[dict[str, Any]] = []
    if current > mean + 3 * std and current > 2 * mean and stats.lines >= 50:
        findings.append(
            {"kind": "volume", "current_per_s": round(current, 3), "mean_per_s": round(mean, 3)}
        )
    err_rates = [r.error_lines_count / max(r.lines_count, 1) for r in runs]
    err_mean = statistics.fmean(err_rates)
    err_std = statistics.pstdev(err_rates)
    cur_err = stats.errors / max(stats.lines, 1)
    if stats.errors >= 5 and cur_err > err_mean + 3 * err_std and cur_err > 2 * err_mean:
        findings.append(
            {"kind": "error_rate", "current": round(cur_err, 3), "mean": round(err_mean, 3)}
        )
    new_mean = statistics.fmean(r.new_patterns_count for r in runs)
    if stats.new_patterns >= 3 and stats.new_patterns > 3 * max(new_mean, 0.5):
        findings.append(
            {
                "kind": "new_patterns",
                "count": stats.new_patterns,
                "templates": stats.new_pattern_templates[:5],
            }
        )
    if not findings:
        return None
    return Fired(
        TriggerType.anomaly,
        {"findings": findings, "baseline_runs": len(runs)},
        "anomalia: " + ", ".join(f["kind"] for f in findings),
    )
