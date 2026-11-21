"""Gera o arquivo .alloy a partir dos hosts e containers monitorados.

Regras (Planning > Coleta de Logs > Grafana Alloy):
- um bloco por host, só para hosts com containers monitorados;
- filtro `keep` pelos IDs Docker dos monitorados;
- `container_id` é o uuid do Lognix, um rule por container;
- labels restritos aos do Modelo de Dados;
- coleta a partir da marcação: `stage.drop { older_than }` descarta histórico antigo, já que
  `loki.source.docker` não tem argumento `since` (verificado na documentação em 2026-11-21).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from typing import Protocol

HEADER = """// Gerado pelo Lognix. Não edite à mão: este arquivo é sobrescrito a cada mudança
// de hosts ou containers monitorados. Histórico em alloy_config_versions.
"""

DROP_OLDER_THAN = "2m"
DISCOVERY_REFRESH = "15s"


class HostLike(Protocol):
    id: uuid.UUID
    name: str


class ContainerLike(Protocol):
    id: uuid.UUID
    docker_id: str
    name: str


def component_id(host_id: uuid.UUID) -> str:
    return "h_" + str(host_id).replace("-", "")[:16]


def _q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _rule(**kwargs: str | Sequence[str]) -> str:
    parts = []
    for key, value in kwargs.items():
        if isinstance(value, str):
            parts.append(f"    {key} = {_q(value)}")
        else:
            inner = ", ".join(_q(v) for v in value)
            parts.append(f"    {key} = [{inner}]")
    return "  rule {\n" + "\n".join(parts) + "\n  }\n"


def render_host(host: HostLike, containers: Sequence[ContainerLike], socket_path: str) -> str:
    cid = component_id(host.id)
    ids = sorted(re.escape(c.docker_id) for c in containers)
    out = [f"// ---- host {host.name} ({host.id}) ----\n"]
    out.append(
        f'discovery.docker "{cid}" {{\n'
        f"  host             = {_q('unix://' + socket_path)}\n"
        f"  refresh_interval = {_q(DISCOVERY_REFRESH)}\n"
        "}\n\n"
    )
    out.append(f'discovery.relabel "{cid}" {{\n')
    out.append(f"  targets = discovery.docker.{cid}.targets\n\n")
    out.append("  // só containers monitorados\n")
    out.append(
        _rule(
            source_labels=["__meta_docker_container_id"],
            regex="(" + "|".join(ids) + ")",
            action="keep",
        )
    )
    out.append("\n  // labels fixos do host\n")
    out.append(_rule(target_label="host", replacement=host.name))
    out.append(_rule(target_label="host_id", replacement=str(host.id)))
    out.append("\n  // nome do container sem a barra inicial\n")
    out.append(
        _rule(
            source_labels=["__meta_docker_container_name"], regex="/(.*)", target_label="container"
        )
    )
    out.append("\n  // container_id do Lognix, um rule por container monitorado\n")
    for c in sorted(containers, key=lambda c: c.docker_id):
        out.append(
            _rule(
                source_labels=["__meta_docker_container_id"],
                regex=re.escape(c.docker_id),
                target_label="container_id",
                replacement=str(c.id),
            )
        )
    out.append("\n  // compose, se existir\n")
    out.append(
        _rule(
            source_labels=["__meta_docker_container_label_com_docker_compose_project"],
            target_label="compose_project",
        )
    )
    out.append(
        _rule(
            source_labels=["__meta_docker_container_label_com_docker_compose_service"],
            target_label="compose_service",
        )
    )
    out.append("}\n\n")
    out.append(
        f'loki.source.docker "{cid}" {{\n'
        f"  host       = {_q('unix://' + socket_path)}\n"
        f"  targets    = discovery.relabel.{cid}.output\n"
        "  forward_to = [loki.process.lognix.receiver]\n"
        "}\n\n"
    )
    return "".join(out)


def render(hosts: Sequence[tuple[HostLike, Sequence[ContainerLike], str]], loki_url: str) -> str:
    """hosts: (host, containers monitorados, caminho do socket do proxy)."""
    out = [HEADER, "\n"]
    for host, containers, socket_path in hosts:
        if containers:
            out.append(render_host(host, containers, socket_path))
    out.append(
        "// ---- pipeline comum ----\n"
        'loki.process "lognix" {\n'
        "  forward_to = [loki.write.default.receiver]\n\n"
        "  // coleta começa na marcação: descarta linhas antigas que o Docker devolve ao\n"
        "  // iniciar a leitura de um container recém-marcado\n"
        "  stage.drop {\n"
        f"    older_than          = {_q(DROP_OLDER_THAN)}\n"
        '    drop_counter_reason = "lognix_before_monitoring"\n'
        "  }\n"
        "}\n\n"
        'loki.write "default" {\n'
        "  endpoint {\n"
        f"    url = {_q(loki_url.rstrip('/') + '/loki/api/v1/push')}\n"
        "  }\n"
        "}\n"
    )
    return "".join(out)
