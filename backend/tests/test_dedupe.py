"""Deduplicação de insights. Ver ADR 016.

Esta lógica decide se uma chamada paga acontece ou não. Errar para o lado frouxo gasta dinheiro
em silêncio; errar para o lado apertado esconde um problema novo do usuário. Os dois erros são
caros, e por isso cada regra do ADR tem um caso aqui.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lognix.ai.dedupe import JANELA_PADRAO, chave, registrar_ocorrencia
from lognix.analysis.models import TriggerFired, TriggerType


def gatilho(tipo: TriggerType = TriggerType.error) -> TriggerFired:
    agora = datetime.now(UTC)
    return TriggerFired(
        id=uuid.uuid4(),
        container_id=uuid.uuid4(),
        type=tipo,
        reason={},
        fired_at=agora,
        window_start=agora - timedelta(seconds=30),
        window_end=agora,
        sample_lines=[],
    )


class TestChave:
    def test_mesmo_erro_com_ids_diferentes_e_o_mesmo_problema(self) -> None:
        """ "falhou para o usuário 12" e "...99" são a mesma falha, e devem ter a mesma chave."""
        g = gatilho()
        a = chave(g, ["pedido 1288 falhou: timeout no gateway"])
        b = chave(g, ["pedido 9931 falhou: timeout no gateway"])
        assert a == b

    def test_uuid_e_hash_tambem_sao_normalizados(self) -> None:
        g = gatilho()
        a = chave(g, ["trace 3f2a1b4c-5d6e-7f80-9a1b-2c3d4e5f6071 falhou"])
        b = chave(g, ["trace 99887766-5544-3322-1100-aabbccddeeff falhou"])
        assert a == b

    def test_erros_diferentes_nao_colidem(self) -> None:
        g = gatilho()
        assert chave(g, ["conexão recusada no postgres"]) != chave(g, ["disco cheio em /var"])

    def test_tipo_de_trigger_separa_problemas_parecidos(self) -> None:
        """Um OOM e um erro de aplicação não são a mesma coisa, mesmo com linhas parecidas."""
        linhas = ["o processo terminou"]
        assert chave(gatilho(TriggerType.error), linhas) != chave(
            gatilho(TriggerType.docker_event), linhas
        )

    def test_a_chave_cabe_na_coluna(self) -> None:
        """A coluna é String(80); uma chave maior estouraria o insert em produção."""
        g = gatilho()
        assert len(chave(g, ["x" * 5000])) <= 80

    def test_ordem_das_amostras_nao_muda_a_chave(self) -> None:
        g = gatilho()
        assert chave(g, ["erro A", "erro B"]) == chave(g, ["erro B", "erro A"])


class TestContagem:
    def test_ocorrencia_soma_e_atualiza_o_visto_por_ultimo(self) -> None:
        from lognix.ai.models import Insight

        g = gatilho()
        insight = Insight(occurrences=3, last_seen_at=datetime.now(UTC) - timedelta(hours=1))
        registrar_ocorrencia(insight, g)
        assert insight.occurrences == 4
        assert insight.last_seen_at == g.window_end


class TestJanela:
    def test_a_janela_padrao_e_de_horas_e_nao_eterna(self) -> None:
        """Dedupe eterno transformaria um erro que volta dias depois numa linha de contador."""
        assert timedelta(hours=1) <= JANELA_PADRAO <= timedelta(days=1)


@pytest.fixture
async def db():
    from lognix.db import get_sessionmaker

    async with get_sessionmaker()() as sessao:
        yield sessao


@pytest.fixture
async def container(db):
    """Host e container de verdade: o insight tem chave estrangeira para o container."""
    from lognix.containers.models import Container, ContainerState
    from lognix.hosts.models import Host, HostStatus, SshAuthMethod

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
        image="x:1",
        labels={},
        env={},
        state=ContainerState.running,
        monitored=True,
    )
    db.add_all([host, c])
    await db.flush()
    return c


class TestNoBanco:
    """As três condições do ADR 016 contra o banco de verdade."""

    @staticmethod
    async def _insight(db, container, chave_: str, visto_em, status="new"):
        from lognix.ai.models import Insight, InsightStatus, Severity

        # insights.trigger_id é NOT NULL: todo insight nasce de uma ocorrência registrada.
        g = TriggerFired(
            id=uuid.uuid4(),
            container_id=container.id,
            type=TriggerType.error,
            reason={},
            fired_at=visto_em,
            window_start=visto_em - timedelta(seconds=30),
            window_end=visto_em,
            sample_lines=[],
        )
        db.add(g)
        await db.flush()
        i = Insight(
            container_id=container.id,
            trigger_id=g.id,
            dedupe_key=chave_,
            occurrences=1,
            last_seen_at=visto_em,
            severity=Severity.high,
            title="t",
            summary="s",
            probable_cause="c",
            suggested_action="a",
            confidence=0.8,
            needs_code=False,
            evidence=[],
            sent_context="",
            status=InsightStatus(status),
        )
        db.add(i)
        await db.flush()
        return i

    async def test_encontra_o_insight_ativo_da_mesma_chave(self, db, container) -> None:
        from lognix.ai.dedupe import insight_ativo

        criado = await self._insight(db, container, "error:abc", datetime.now(UTC))
        achado = await insight_ativo(db, container_id=container.id, dedupe_key="error:abc")
        assert achado is not None and achado.id == criado.id

    async def test_fora_da_janela_nao_conta(self, db, container) -> None:
        """Passado o tempo, o problema é novo: o contexto mudou e a causa pode ser outra."""
        from lognix.ai.dedupe import insight_ativo

        await self._insight(db, container, "error:abc", datetime.now(UTC) - timedelta(hours=9))
        assert await insight_ativo(db, container_id=container.id, dedupe_key="error:abc") is None

    async def test_insight_ja_visto_nao_bloqueia_um_novo(self, db, container) -> None:
        """Dedupe é contra ruído, não contra notícia: depois de tratado, reaparecer é novidade."""
        from lognix.ai.dedupe import insight_ativo

        await self._insight(db, container, "error:abc", datetime.now(UTC), status="seen")
        assert await insight_ativo(db, container_id=container.id, dedupe_key="error:abc") is None

    async def test_outro_container_nao_compartilha_insight(self, db, container) -> None:
        from lognix.ai.dedupe import insight_ativo

        await self._insight(db, container, "error:abc", datetime.now(UTC))
        achado = await insight_ativo(db, container_id=uuid.uuid4(), dedupe_key="error:abc")
        assert achado is None
