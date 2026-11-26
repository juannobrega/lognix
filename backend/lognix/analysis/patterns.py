"""Agrupamento de linhas em padrões com Drain (drain3), um minerador por container."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

# Normalizações baratas antes do Drain: timestamps, hex longos, uuids, IPs, números.
_PRE = [
    (
        re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"),
        "<TS>",
    ),
    (re.compile(r"\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}"), "<TS>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "<UUID>"),
    (re.compile(r"\b[0-9a-f]{24,64}\b"), "<HEX>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<IP>"),
]


def normalize(line: str) -> str:
    out = line.strip()
    for rx, rep in _PRE:
        out = rx.sub(rep, out)
    return out[:1000]


@dataclass
class MinedLine:
    cluster_id: int
    template: str
    is_new: bool


class PatternMiner:
    def __init__(self) -> None:
        cfg = TemplateMinerConfig()
        cfg.drain_depth = 4
        cfg.drain_sim_th = 0.4
        cfg.drain_max_children = 100
        cfg.drain_max_clusters = 2000
        cfg.mask_prefix = "<"
        cfg.mask_suffix = ">"
        self._miner = TemplateMiner(config=cfg)

    def add(self, line: str) -> MinedLine:
        result = self._miner.add_log_message(normalize(line))
        return MinedLine(
            cluster_id=int(result["cluster_id"]),
            template=str(result["template_mined"]),
            is_new=result["change_type"] == "cluster_created",
        )

    def seed(self, samples: list[str]) -> None:
        """Reconstrói clusters aproximados a partir de amostras guardadas no banco."""
        for sample in samples:
            self._miner.add_log_message(normalize(sample))

    def template_of(self, cluster_id: int) -> str | None:
        cluster = self._miner.drain.id_to_cluster.get(cluster_id)
        return cluster.get_template() if cluster is not None else None

    @property
    def cluster_count(self) -> int:
        return len(self._miner.drain.clusters)


_miners: dict[uuid.UUID, PatternMiner] = {}


def miner_for(container_id: uuid.UUID) -> PatternMiner:
    miner = _miners.get(container_id)
    if miner is None:
        miner = _miners[container_id] = PatternMiner()
    return miner


def drop_miner(container_id: uuid.UUID) -> None:
    _miners.pop(container_id, None)
