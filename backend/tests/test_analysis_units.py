import uuid
from datetime import UTC, datetime, timedelta

from lognix.analysis import triggers as trig
from lognix.analysis.classifier import classify
from lognix.analysis.models import AnalysisRun, LogLevel, RunStatus, TriggerType
from lognix.analysis.patterns import PatternMiner, normalize
from lognix.events.models import DockerEvent, DockerEventType


def test_classify_structured_and_regex() -> None:
    assert classify('{"level":"error","msg":"x"}') == LogLevel.error
    assert classify('{"severity":"WARNING"}') == LogLevel.warn
    assert classify('{"level":50,"msg":"pino"}') == LogLevel.error
    assert classify('{"level":30}') == LogLevel.info
    assert classify("2026-11-22 ERROR db down") == LogLevel.error
    assert classify("Traceback (most recent call last):") == LogLevel.error
    assert classify("2026/11/21 [error] 30#30: connect() failed") == LogLevel.error
    assert classify("level=warn msg=slow") == LogLevel.warn
    assert classify("INFO: started") == LogLevel.info
    assert classify("GET /health 200") == LogLevel.unknown
    assert classify("ERRORS_TOTAL=0") == LogLevel.unknown  # palavra inteira apenas


def test_normalize_masks_variable_tokens() -> None:
    out = normalize(
        "2026-11-22T10:00:00Z user 3f2a6c0e-1b2c-4d5e-8f90-aaaaaaaaaaaa from 10.0.0.1:443 id 0123456789abcdef0123456789abcdef"
    )
    assert out == "<TS> user <UUID> from <IP> id <HEX>"


def test_pattern_miner_groups_lines() -> None:
    m = PatternMiner()
    a = m.add("user 42 logged in from 10.0.0.1")
    b = m.add("user 7 logged in from 10.0.0.9")
    c = m.add("connection refused: db:5432")
    assert a.is_new and not b.is_new and c.is_new
    assert a.cluster_id == b.cluster_id != c.cluster_id
    assert "logged in" in b.template
    assert m.cluster_count == 2


def _run(lines: int, errors: int, new: int = 0, secs: int = 30) -> AnalysisRun:
    end = datetime.now(UTC)
    return AnalysisRun(
        container_id=uuid.uuid4(),
        window_start=end - timedelta(seconds=secs),
        window_end=end,
        lines_count=lines,
        error_lines_count=errors,
        new_patterns_count=new,
        status=RunStatus.ok,
        manual=False,
    )


def test_trigger_error_and_anomaly() -> None:
    assert trig.evaluate_error(trig.WindowStats(10, 0, 0, 0, 30)) is None
    f = trig.evaluate_error(trig.WindowStats(10, 2, 0, 0, 30))
    assert f and f.type == TriggerType.error and f.reason["error_lines"] == 2

    baseline = [_run(30, 0) for _ in range(15)]
    assert trig.evaluate_anomaly(trig.WindowStats(35, 0, 0, 0, 30), baseline) is None
    volume = trig.evaluate_anomaly(trig.WindowStats(900, 0, 0, 0, 30), baseline)
    assert (
        volume
        and volume.type == TriggerType.anomaly
        and volume.reason["findings"][0]["kind"] == "volume"
    )
    assert (
        trig.evaluate_anomaly(trig.WindowStats(900, 0, 0, 0, 30), baseline[:5]) is None
    )  # baseline curta
    newp = trig.evaluate_anomaly(
        trig.WindowStats(30, 0, 0, 6, 30, new_pattern_templates=["a"]), baseline
    )
    assert newp and any(f["kind"] == "new_patterns" for f in newp.reason["findings"])


def test_trigger_docker_events() -> None:
    cid = uuid.uuid4()
    now = datetime.now(UTC)

    def ev(t: DockerEventType, offset: int = 0, **kw: object) -> DockerEvent:
        return DockerEvent(
            container_id=cid,
            type=t,
            occurred_at=now + timedelta(seconds=offset),
            attributes={},
            **kw,
        )  # type: ignore[arg-type]

    assert (
        trig.evaluate_docker_events(
            [ev(DockerEventType.start), ev(DockerEventType.die, exit_code=0)]
        )
        is None
    )
    f = trig.evaluate_docker_events([ev(DockerEventType.die, exit_code=137)])
    assert f and f.reason["events"][0]["exit_code"] == 137
    assert (
        trig.evaluate_docker_events([ev(DockerEventType.restart, i * 60) for i in range(2)]) is None
    )
    loop = trig.evaluate_docker_events([ev(DockerEventType.restart, i * 60) for i in range(3)])
    assert loop and loop.reason["events"][0]["type"] == "restart_loop"
    unhealthy = ev(DockerEventType.health_status)
    unhealthy.attributes = {"action": "health_status: unhealthy"}
    assert trig.evaluate_docker_events([unhealthy]) is not None
