import re
import uuid
from dataclasses import dataclass

from lognix.alloy.generator import component_id, render


@dataclass
class H:
    id: uuid.UUID
    name: str


@dataclass
class C:
    id: uuid.UUID
    docker_id: str
    name: str


def test_render_without_hosts_has_only_common_pipeline() -> None:
    out = render([], "http://loki:3100")
    assert "discovery.docker" not in out
    assert 'loki.process "lognix"' in out
    assert "older_than" in out
    assert 'url = "http://loki:3100/loki/api/v1/push"' in out


def test_render_host_block() -> None:
    host = H(uuid.uuid4(), "vm-01")
    c1 = C(uuid.uuid4(), "9c1d" + "0" * 60, "api")
    c2 = C(uuid.uuid4(), "77ab" + "0" * 60, "db")
    out = render([(host, [c1, c2], f"/tunnels/{host.id}.sock")], "http://loki:3100/")
    cid = component_id(host.id)
    assert f'discovery.docker "{cid}"' in out
    assert f'host             = "unix:///tunnels/{host.id}.sock"' in out
    # keep só dos monitorados, em ordem determinística
    keep = re.search(r'regex = "\((.*?)\)"\n    action = "keep"', out)
    assert keep and keep.group(1) == "|".join(sorted([c1.docker_id, c2.docker_id]))
    # container_id do Lognix por container
    assert f'replacement = "{c1.id}"' in out and f'replacement = "{c2.id}"' in out
    assert 'target_label = "host"\n    replacement = "vm-01"' in out
    # labels permitidos apenas
    labels = set(re.findall(r'target_label = "([a-z_]+)"', out))
    assert labels == {
        "host",
        "host_id",
        "container",
        "container_id",
        "compose_project",
        "compose_service",
    }
    # source sem refresh_interval (obsoleto) e encaminhando ao process
    src = out[out.index("loki.source.docker") :]
    assert "refresh_interval" not in src.split("}")[0]
    assert "forward_to = [loki.process.lognix.receiver]" in out


def test_host_without_monitored_is_omitted() -> None:
    host = H(uuid.uuid4(), "vm-02")
    out = render([(host, [], "/tunnels/x.sock")], "http://loki:3100")
    assert "vm-02" not in out


def test_render_is_deterministic() -> None:
    host = H(uuid.uuid4(), "vm-01")
    cs = [C(uuid.uuid4(), f"{i:02d}" + "0" * 62, f"c{i}") for i in range(5)]
    a = render([(host, cs, "/t.sock")], "http://l")
    b = render([(host, list(reversed(cs)), "/t.sock")], "http://l")
    assert a == b
