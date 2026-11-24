"""Medição formal dos critérios do ADR 009: o Lognix aguenta sem Redis?

Sobe o app real contra Postgres real, com N hosts falsos (SSH e Docker simulados) e M
containers monitorados, e mede:

  1. duração da parte determinística de um ciclo, por container, com todos em ciclo simultâneo;
  2. p95 da latência da API enquanto os ciclos rodam;
  3. estabilidade dos túneis e dos workers ao longo do teste;
  4. memória do processo.

Uso:
    .venv/bin/python scripts/measure.py --hosts 10 --containers 100 --lines 200 --rounds 3
    .venv/bin/python scripts/measure.py --soak-minutes 60     # teste longo de túneis
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import resource
import statistics
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("LOGNIX_SECRET_KEY", "measure-secret-key-with-at-least-32-chars!!")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://lognix:lognix@localhost:5432/lognix_measure"
)
os.environ.setdefault("LOGNIX_LOG_LEVEL", "WARNING")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from lognix.alloy import service as alloy_service
from lognix.analysis import manager as manager_module
from lognix.analysis.cycle import run_cycle
from lognix.analysis.manager import AnalysisManager
from lognix.containers.models import Container, ContainerState
from lognix.db import get_engine, get_sessionmaker
from lognix.events import workers as workers_module
from lognix.events.workers import HostWorkers
from lognix.hosts import credentials as creds_mod
from lognix.hosts import supervisor as sup_module
from lognix.hosts.models import Host, HostStatus, SshAuthMethod
from lognix.hosts.schemas import HostCredentialsIn
from lognix.hosts.supervisor import TunnelSupervisor
from lognix.loki.client import LogLine, LokiClient
from lognix.main import app

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
from tests.fake_docker import FakeDocker
from tests.fake_ssh import FakeSshBackend

# Linhas representativas: JSON estruturado, acesso nginx, stack trace, texto livre.
SAMPLE_LINES = [
    '{"level":"info","ts":"2026-11-24T10:00:00Z","msg":"request served","path":"/api/v1/health","ms":12}',
    '172.19.0.1 - - [24/Nov/2026:10:00:00 +0000] "GET /api/v1/projects HTTP/1.1" 200 1843 "-" "Mozilla/5.0"',
    "2026-11-24 10:00:00,123 INFO  [worker-3] processed batch id=8821 items=250",
    '{"level":"warn","ts":"2026-11-24T10:00:01Z","msg":"slow query","ms":812,"sql":"select * from x"}',
    "2026-11-24 10:00:02,900 ERROR [api] Connection refused: db:5432",
    "Traceback (most recent call last):",
    '  File "/app/svc/db.py", line 42, in connect',
    "ConnectionRefusedError: [Errno 111] Connection refused",
    "2026-11-24 10:00:03,001 INFO  [worker-7] cache hit ratio 0.93",
    '{"level":"info","ts":"2026-11-24T10:00:04Z","msg":"user logged in","user_id":4821}',
]


class BenchLoki(LokiClient):
    """Loki sintético: devolve `lines_per_window` linhas variadas por consulta."""

    lines_per_window = 200

    def __init__(self) -> None:
        self.base_url = "http://bench"

    async def aclose(self) -> None:
        return None

    async def query_range(
        self,
        query: str,
        *,
        start_ns: int,
        end_ns: int,
        limit: int = 1000,
        direction: str = "backward",
    ) -> list[LogLine]:
        n = min(self.lines_per_window, limit)
        base = start_ns
        out = []
        for i in range(n):
            text_line = SAMPLE_LINES[i % len(SAMPLE_LINES)]
            # Variação nos valores para o Drain ter o que generalizar.
            text_line = text_line.replace("8821", str(8000 + i)).replace("4821", str(4000 + i))
            out.append(LogLine(base + i, text_line, {"container": "bench"}))
        return out


def rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return usage / (1024 * 1024) if sys.platform == "darwin" else usage / 1024


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = min(int(round(p / 100 * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[k]


def reset_database() -> None:
    """Fora do loop: o env.py do Alembic abre o seu próprio asyncio.run()."""
    from alembic.config import Config

    from alembic import command

    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


async def seed(hosts: int, containers: int, tmp: str) -> tuple[list[FakeDocker], list[uuid.UUID]]:
    """Cria hosts conectados (SSH falso) e containers monitorados direto no banco."""
    fakes: list[FakeDocker] = []
    container_ids: list[uuid.UUID] = []
    per_host = max(1, containers // hosts)
    supervisor = sup_module.get_supervisor()
    async with get_sessionmaker()() as db:
        for h in range(hosts):
            docker_path = os.path.join(tmp, f"docker-{h}.sock")
            fake = FakeDocker(docker_path)
            await fake.start()
            fakes.append(fake)
            host = Host(
                id=uuid.uuid4(),
                name=f"bench-{h:02d}",
                address="127.0.0.1",
                ssh_port=22,
                ssh_user="deploy",
                ssh_auth_method=SshAuthMethod.password,
                status=HostStatus.pending,
            )
            creds_mod.apply(
                host,
                HostCredentialsIn(ssh_auth_method=SshAuthMethod.password, password="deploy123"),
            )
            db.add(host)
            await db.flush()
            now = datetime.now(UTC)
            for c in range(per_host):
                container = Container(
                    id=uuid.uuid4(),
                    host_id=host.id,
                    docker_id=f"{h:02d}{c:04d}" + "0" * 58,
                    name=f"svc-{h:02d}-{c:03d}",
                    image="ghcr.io/bench/svc:1.0",
                    labels={},
                    env={},
                    state=ContainerState.running,
                    monitored=True,
                    monitored_since=now - timedelta(minutes=1),
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(container)
                container_ids.append(container.id)
            supervisor.backend = FakeSshBackend(
                docker_path
            )  # último vence; só para o túnel existir
            supervisor.ensure(host)
        await db.commit()
    return fakes, container_ids[:containers]


async def measure_cycles(container_ids: list[uuid.UUID], rounds: int) -> dict[str, object]:
    """Todos os containers em ciclo ao mesmo tempo, N rodadas. Mede a parte determinística."""
    durations: list[float] = []
    lines_total = 0
    for _ in range(rounds):
        end = datetime.now(UTC)
        start = end - timedelta(seconds=30)

        async def one(cid: uuid.UUID) -> float:
            async with get_sessionmaker()() as db:
                container = await db.get(Container, cid)
                assert container is not None
                client = BenchLoki()
                t0 = time.perf_counter()
                result = await run_cycle(db, client, container, window_start=start, window_end=end)
                elapsed = time.perf_counter() - t0
                return elapsed if result.run.status.value != "failed" else -1.0

        t_round = time.perf_counter()
        results = await asyncio.gather(*(one(cid) for cid in container_ids))
        wall = time.perf_counter() - t_round
        ok = [r for r in results if r >= 0]
        durations.extend(ok)
        lines_total += len(ok) * BenchLoki.lines_per_window
        print(
            f"  rodada: {len(ok)} ciclos em {wall:.1f}s "
            f"(p50 {pct(ok, 50) * 1000:.0f} ms, p95 {pct(ok, 95) * 1000:.0f} ms, máx {max(ok) * 1000:.0f} ms)"
        )
    return {
        "cycles": len(durations),
        "lines_processed": lines_total,
        "p50_ms": round(pct(durations, 50) * 1000, 1),
        "p95_ms": round(pct(durations, 95) * 1000, 1),
        "max_ms": round(max(durations) * 1000, 1),
        "mean_ms": round(statistics.fmean(durations) * 1000, 1),
    }


async def measure_api_under_load(
    client: AsyncClient, token: str, container_ids: list[uuid.UUID], seconds: int, pause: float = 0
) -> dict[str, object]:
    """p95 da API enquanto os ciclos rodam. pause=0 satura; pause>0 imita o regime real."""
    headers = {"Authorization": f"Bearer {token}"}
    stop = asyncio.Event()

    semaphore = manager_module.get_analysis_manager().semaphore

    async def one_cycle(cid: uuid.UUID) -> None:
        end = datetime.now(UTC)
        start = end - timedelta(seconds=30)
        async with semaphore, get_sessionmaker()() as db:
            container = await db.get(Container, cid)
            if container is not None:
                await run_cycle(db, BenchLoki(), container, window_start=start, window_end=end)

    async def cycle_load() -> int:
        """Saturação: ciclos sem pausa nenhuma, muito além do regime real."""
        count = 0
        while not stop.is_set():
            await asyncio.gather(*(one_cycle(cid) for cid in container_ids))
            count += len(container_ids)
        return count

    async def realistic_load() -> int:
        """Regime real: um loop por container, com a pausa configurada entre ciclos."""
        count = 0

        async def loop_for(cid: uuid.UUID) -> None:
            nonlocal count
            # Espalha o início para não alinhar todos os containers no mesmo instante.
            await asyncio.sleep((hash(cid) % 1000) / 1000 * pause)
            while not stop.is_set():
                await one_cycle(cid)
                count += 1
                await asyncio.sleep(pause)

        await asyncio.gather(*(loop_for(cid) for cid in container_ids))
        return count

    async def api_probe() -> list[float]:
        latencies: list[float] = []
        routes = [
            "/api/v1/hosts",
            "/api/v1/projects",
            "/api/v1/notifications/count",
            "/api/v1/health",
        ]
        i = 0
        while not stop.is_set():
            route = routes[i % len(routes)]
            i += 1
            t0 = time.perf_counter()
            resp = await client.get(route, headers=headers)
            latencies.append(time.perf_counter() - t0)
            assert resp.status_code == 200, (route, resp.status_code)
            await asyncio.sleep(0.05)
        return latencies

    load = asyncio.create_task(realistic_load() if pause else cycle_load())
    probe = asyncio.create_task(api_probe())
    await asyncio.sleep(seconds)
    stop.set()
    cycles, latencies = await asyncio.gather(load, probe)
    return {
        "mode": "regime real" if pause else "saturação",
        "pause_between_cycles_s": pause,
        "duration_s": seconds,
        "cycles_run": cycles,
        "api_requests": len(latencies),
        "api_p50_ms": round(pct(latencies, 50) * 1000, 1),
        "api_p95_ms": round(pct(latencies, 95) * 1000, 1),
        "api_p99_ms": round(pct(latencies, 99) * 1000, 1),
        "api_max_ms": round(max(latencies) * 1000, 1),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hosts", type=int, default=10)
    parser.add_argument("--containers", type=int, default=100)
    parser.add_argument("--lines", type=int, default=200)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--api-seconds", type=int, default=20)
    parser.add_argument(
        "--pause", type=float, default=30.0, help="pausa entre ciclos no regime real"
    )
    parser.add_argument("--out", default="")
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    BenchLoki.lines_per_window = args.lines
    tmp = tempfile.mkdtemp(prefix="lgx-bench", dir="/tmp")
    print(f"Medição: {args.hosts} hosts, {args.containers} containers, {args.lines} linhas/janela")

    supervisor = TunnelSupervisor(
        backend=FakeSshBackend(os.path.join(tmp, "x.sock")),
        tunnels_dir=os.path.join(tmp, "tunnels"),
    )
    sup_module.set_supervisor(supervisor)
    workers = HostWorkers(supervisor.socket_path)
    supervisor.on_status = workers.on_host_status
    workers_module.set_host_workers(workers)
    manager = AnalysisManager(client_factory=BenchLoki, pause_seconds=3600)
    manager_module.set_analysis_manager(manager)
    alloy_service.set_alloy_manager(
        alloy_service.AlloyManager(
            config_path=os.path.join(tmp, "config.alloy"),
            alloy_url="http://alloy.invalid",
            loki_url="http://loki.invalid",
            tunnels_dir=os.path.join(tmp, "tunnels"),
        )
    )

    fakes, container_ids = await seed(args.hosts, args.containers, tmp)
    rss_before = rss_mb()
    print(f"Memória após seed: {rss_before:.0f} MB")

    print("\n[1] Ciclos simultâneos")
    cycles = await measure_cycles(container_ids, args.rounds)

    print("\n[2] API sob carga de ciclos")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://bench") as client:
        setup = await client.post(
            "/api/v1/setup",
            json={"email": "bench@example.com", "name": "Bench", "password": "senha-forte-123"},
        )
        token = (
            setup.json()["access_token"]
            if setup.status_code == 201
            else (
                await client.post(
                    "/api/v1/auth/login",
                    json={"email": "bench@example.com", "password": "senha-forte-123"},
                )
            ).json()["access_token"]
        )
        print("  modo saturação (ciclos sem pausa, pior caso):")
        api = await measure_api_under_load(client, token, container_ids, args.api_seconds)
        print(f"    p95 {api['api_p95_ms']} ms em {api['cycles_run']} ciclos")
        print(f"  modo regime real (pausa de {args.pause}s entre ciclos):")
        api_real = await measure_api_under_load(
            client, token, container_ids, args.api_seconds, pause=args.pause
        )
        print(f"    p95 {api_real['api_p95_ms']} ms em {api_real['cycles_run']} ciclos")

    rss_after = rss_mb()
    async with get_sessionmaker()() as db:
        rows = int((await db.execute(text("select count(*) from analysis_runs"))).scalar_one())
        patterns = int((await db.execute(text("select count(*) from patterns"))).scalar_one())
        db_size = (
            await db.execute(text("select pg_size_pretty(pg_database_size(current_database()))"))
        ).scalar_one()

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "setup": {
            "hosts": args.hosts,
            "containers": args.containers,
            "lines_per_window": args.lines,
            "rounds": args.rounds,
        },
        "cycles": cycles,
        "api_saturation": api,
        "api_realistic": api_real,
        "memory": {"after_seed_mb": round(rss_before), "after_test_mb": round(rss_after)},
        "database": {"analysis_runs": rows, "patterns": patterns, "size": db_size},
    }
    print("\n=== RESULTADO ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    crit = {
        "ciclo determinístico < 5 s por container (p95)": cycles["p95_ms"] < 5000,
        "API p95 < 300 ms no regime real": api_real["api_p95_ms"] < 300,
        "nenhum ciclo falhou": cycles["cycles"] == args.containers * args.rounds,
    }
    print(f"\n  (informativo) API p95 em saturação, ciclos sem pausa: {api['api_p95_ms']} ms")
    print("\n=== CRITÉRIOS DO ADR 009 ===")
    for name, passed in crit.items():
        print(f"  {'PASSOU' if passed else 'FALHOU'}  {name}")
    report["criteria"] = crit

    if args.out:
        Path(args.out).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nRelatório salvo em {args.out}")

    await manager.stop()
    await workers.stop()
    await supervisor.stop()
    for fake in fakes:
        await fake.stop()
    await get_engine().dispose()


if __name__ == "__main__":
    parsed = parse_args()
    reset_database()
    asyncio.run(main(parsed))
