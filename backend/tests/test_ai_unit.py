import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lognix.ai.context import build_context, estimate_tokens, truncate_middle
from lognix.ai.schemas import SchemaError, validate_insight
from lognix.ai.service import parse_json_object
from lognix.analysis.models import LogLevel, Pattern, TriggerFired, TriggerType
from lognix.containers.models import Container, ContainerState
from lognix.events.models import DockerEvent, DockerEventType
from lognix.hosts.models import Host, HostStatus, SshAuthMethod
from lognix.loki.client import LogLine
from tests.fake_ai import VALID_INSIGHT


def test_parse_json_object_handles_wrappers() -> None:
    assert parse_json_object('{"a": 1}') == {"a": 1}
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('Claro! Aqui está:\n{"a": 1}\nEspero ter ajudado.') == {"a": 1}
    with pytest.raises(SchemaError):
        parse_json_object("sem json aqui")
    with pytest.raises(SchemaError):
        parse_json_object("{quebrado")


def test_validate_insight_accepts_and_normalizes() -> None:
    out = validate_insight(dict(VALID_INSIGHT), max_index={"log_line": 2})
    assert out["severity"] == "high" and out["confidence"] == 0.82
    assert out["evidence_refs"] == [{"kind": "log_line", "index": 0}]


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        ({"severity": "urgentíssimo"}, "severity"),
        ({"title": ""}, "title"),
        ({"confidence": 1.5}, "entre 0 e 1"),
        ({"confidence": "alta"}, "número"),
        ({"needs_code": "sim"}, "true ou false"),
        ({"evidence_refs": []}, "ao menos uma"),
        ({"evidence_refs": [{"kind": "arquivo", "index": 0}]}, "kind"),
        ({"evidence_refs": [{"kind": "log_line", "index": 99}]}, "não existe no contexto"),
        ({"inventado": 1}, "não previstos"),
    ],
)
def test_validate_insight_rejects(mutate: dict, fragment: str) -> None:  # type: ignore[type-arg]
    with pytest.raises(SchemaError, match=fragment):
        validate_insight({**VALID_INSIGHT, **mutate}, max_index={"log_line": 2})


def test_truncate_middle_keeps_both_ends() -> None:
    line = "A" * 500 + "MEIO" + "B" * 500
    out = truncate_middle(line, limit=200)
    assert out.startswith("AAA") and out.endswith("BBB") and "omitidos" in out
    assert len(out) < len(line)
    assert truncate_middle("curta", limit=200) == "curta"


def _fixture_container() -> Container:
    host = Host(
        id=uuid.uuid4(),
        name="vm-01",
        address="10.0.0.1",
        ssh_port=22,
        ssh_user="deploy",
        ssh_auth_method=SshAuthMethod.password,
        status=HostStatus.connected,
    )
    c = Container(
        id=uuid.uuid4(),
        host_id=host.id,
        docker_id="abc",
        name="api",
        image="ghcr.io/x/api:1.5.0",
        labels={},
        env={"safe": {"APP_VERSION": "1.5.0"}},
        state=ContainerState.running,
        monitored=True,
    )
    c.host = host
    return c


def _trigger(container: Container, type_: TriggerType = TriggerType.error) -> TriggerFired:
    now = datetime.now(UTC)
    return TriggerFired(
        id=uuid.uuid4(),
        container_id=container.id,
        type=type_,
        reason={},
        fired_at=now,
        window_start=now - timedelta(seconds=30),
        window_end=now,
        note="2 linhas de erro",
    )


def test_build_context_numbers_evidence_and_includes_blocks() -> None:
    c = _fixture_container()
    lines = [LogLine(1_000_000_000 * (i + 1), f"linha {i}", {}) for i in range(10)]
    lines.append(LogLine(11_000_000_000, "ERROR db down", {}))
    levels = {10: LogLevel.error}
    pattern = Pattern(
        id=uuid.uuid4(),
        container_id=c.id,
        template="ERROR db <*>",
        level=LogLevel.error,
        count_total=7,
        sample="ERROR db down",
    )
    event = DockerEvent(
        container_id=c.id,
        type=DockerEventType.redeploy,
        attributes={},
        previous_image="api:1.4.0",
        new_image="api:1.5.0",
        occurred_at=datetime.now(UTC),
    )
    ctx = build_context(
        container=c,
        trigger=_trigger(c),
        lines=lines,
        levels=levels,
        events=[event],
        patterns=[pattern],
        new_pattern_templates=["ERROR db <*>"],
        state={"state": "running"},
        max_input_tokens=12000,
    )
    assert "[PROJETO]" in ctx.user_text and "api" in ctx.user_text
    assert "APP_VERSION=1.5.0" in ctx.user_text
    assert "[LINHAS DE ERRO]" in ctx.user_text and "[log_line 0] " in ctx.user_text
    assert "[CONTEXTO ANTERIOR]" in ctx.user_text
    assert "[EVENTOS DOCKER]" in ctx.user_text and "[docker_event 0]" in ctx.user_text
    assert "[PADRÕES]" in ctx.user_text and "NOVO" in ctx.user_text
    assert "[REDEPLOY]" in ctx.user_text and "api:1.4.0 → api:1.5.0" in ctx.user_text
    assert "[ESTADO ATUAL]" in ctx.user_text
    assert ctx.max_index() == {"log_line": 1, "docker_event": 1, "pattern": 1}
    assert not ctx.truncated

    resolved = ctx.resolve([{"kind": "log_line", "index": 0}, {"kind": "pattern", "index": 0}])
    assert resolved[0]["text"] == "ERROR db down"
    assert resolved[1]["text"] == "ERROR db <*>" and resolved[1]["count"] == 7


def test_build_context_truncates_to_budget() -> None:
    c = _fixture_container()
    lines = [
        LogLine(1_000_000_000 * (i + 1), f"ERROR falha número {i} " + "x" * 300, {})
        for i in range(100)
    ]
    levels = {i: LogLevel.error for i in range(100)}
    ctx = build_context(
        container=c,
        trigger=_trigger(c),
        lines=lines,
        levels=levels,
        events=[],
        patterns=[],
        new_pattern_templates=[],
        state=None,
        max_input_tokens=800,
    )
    assert ctx.truncated
    assert ctx.estimated_tokens <= 1200  # cabe perto do orçamento após os cortes
    # As evidências remanescentes continuam numeradas de 0 em diante, sem buracos.
    indexes = [e.index for e in ctx.evidences["log_line"]]
    assert indexes == list(range(len(indexes)))


def test_build_context_collapses_repeated_errors() -> None:
    c = _fixture_container()
    lines = [
        LogLine(1_000_000_000 * (i + 1), f"ERROR conexão {i} recusada " + "y" * 200, {})
        for i in range(60)
    ]
    levels = {i: LogLevel.error for i in range(60)}
    ctx = build_context(
        container=c,
        trigger=_trigger(c),
        lines=lines,
        levels=levels,
        events=[],
        patterns=[],
        new_pattern_templates=[],
        state=None,
        max_input_tokens=900,
    )
    assert ctx.truncated
    assert "repetida" in ctx.user_text or len(ctx.evidences["log_line"]) < 60


def test_estimate_tokens_is_monotonic() -> None:
    assert estimate_tokens("abc") < estimate_tokens("abc" * 100)
    assert estimate_tokens("") >= 1
    _ = json


class TestProviderSpecs:
    """A lista de providers virou dado. Dado errado quebra em produção, não no import."""

    def test_todo_kind_tem_spec_coerente(self) -> None:
        from lognix.ai.providers.base import SPECS, ProviderKind

        assert set(SPECS) == set(ProviderKind), "kind sem entrada em SPECS"
        for kind, spec in SPECS.items():
            assert spec.kind == kind, f"{kind}: spec aponta para outro kind"
            assert spec.label.strip(), f"{kind}: sem rótulo"
            keys = [f["key"] for f in spec.fields]
            assert keys, f"{kind}: nenhum campo de credencial"
            assert len(keys) == len(set(keys)), f"{kind}: campo repetido"
            assert any(f["required"] for f in spec.fields), f"{kind}: nada obrigatório"
            for f in spec.fields:
                assert set(f) >= {"key", "label", "secret", "required", "placeholder", "help"}

    def test_url_base_so_falta_em_quem_tem_protocolo_proprio(self) -> None:
        from lognix.ai.providers.base import SPECS, ProviderKind

        proprios = {ProviderKind.anthropic, ProviderKind.bedrock}
        for kind, spec in SPECS.items():
            if kind in proprios:
                assert spec.base_url is None, f"{kind}: tem protocolo próprio, não URL de chat"
            else:
                # Quem fala o dialeto da OpenAI precisa saber para onde falar: ou o spec traz o
                # padrão, ou o usuário é obrigado a informar. Sem nenhum dos dois, o cliente
                # sairia batendo em api.openai.com com a credencial de outro serviço.
                pede_ao_usuario = any(f["key"] == "base_url" and f["required"] for f in spec.fields)
                assert spec.base_url or pede_ao_usuario, f"{kind}: ninguém define a URL base"
                if spec.base_url:
                    assert spec.base_url.startswith("http"), f"{kind}: URL base estranha"
                    assert not spec.base_url.endswith("/"), f"{kind}: URL base com barra no fim"

    def test_credencial_que_falta_e_recusada_antes_da_rede(self) -> None:
        import pytest

        from lognix.ai.provider import AiError
        from lognix.ai.providers import build_provider
        from lognix.ai.providers.base import SPECS

        for kind, spec in SPECS.items():
            obrigatorios = [f for f in spec.fields if f["required"]]
            if not obrigatorios:
                continue  # Ollama roda local e não exige chave
            with pytest.raises(AiError, match="Falta preencher"):
                build_provider(kind, {})

    def test_cada_tipo_monta_um_cliente_com_o_nome_certo(self) -> None:
        from lognix.ai.providers import build_provider
        from lognix.ai.providers.base import SPECS

        valores = {
            "api_key": "k",
            "region": "us-east-1",
            "access_key_id": "AKIA",
            "secret_access_key": "s",
            # O Ollama exige endereço: o padrão é localhost, que de dentro do contêiner do
            # Lognix aponta para o próprio contêiner, não para a máquina de quem instalou.
            "base_url": "http://192.168.0.10:11434/v1",
            "organization": "",
        }
        for kind, spec in SPECS.items():
            client = build_provider(kind, valores)
            assert client.kind == str(kind), f"{kind}: cliente reporta kind errado"
            # O nome aparece nas mensagens de erro: trocado, manda conferir a credencial errada.
            assert client.name == spec.label, f"{kind}: cliente se apresenta como {client.name}"
