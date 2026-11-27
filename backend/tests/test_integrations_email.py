"""Alertas por e-mail. Ver ADR 020.

O envio é testado contra um `smtplib` falsificado: a suíte não pode depender de servidor SMTP,
e o que importa aqui é **o que** sai e **quando** sai, não a implementação do protocolo.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from typing import Any

import pytest
from httpx import AsyncClient

from lognix.integrations import alerts, smtp
from lognix.integrations.smtp import Conta, EnvioError

ROTA = "/api/v1/integrations/email"


@dataclass
class ServidorFalso:
    """Registra o que o `smtplib` receberia. Um por teste."""

    enviados: list[Any] = field(default_factory=list)
    logins: list[tuple[str, str]] = field(default_factory=list)
    starttls: int = 0
    erro: Exception | None = None
    ssl_direto: bool = False

    def classe(self, direto: bool = False):
        servidor = self

        class Falso:
            def __init__(self, host: str, port: int, **kw: Any) -> None:
                servidor.ssl_direto = direto
                self.host, self.port = host, port

            def __enter__(self):
                return self

            def __exit__(self, *a: Any) -> None:
                return None

            def ehlo(self) -> None:
                return None

            def starttls(self, **kw: Any) -> None:
                servidor.starttls += 1

            def login(self, u: str, p: str) -> None:
                if servidor.erro:
                    raise servidor.erro
                servidor.logins.append((u, p))

            def send_message(self, msg: Any) -> None:
                if servidor.erro:
                    raise servidor.erro
                servidor.enviados.append(msg)

        return Falso


@pytest.fixture
def servidor(monkeypatch) -> ServidorFalso:
    s = ServidorFalso()
    monkeypatch.setattr(smtplib, "SMTP", s.classe())
    monkeypatch.setattr(smtplib, "SMTP_SSL", s.classe(direto=True))
    return s


def conta(**kw: Any) -> Conta:
    base = {
        "host": "smtp.exemplo.com",
        "port": 587,
        "security": "starttls",
        "username": "u",
        "password": "p",
        "remetente": "lognix@exemplo.com",
        "destinatarios": ["ops@exemplo.com"],
    }
    return Conta(**{**base, **kw})


# --- catálogo -----------------------------------------------------------------------------


def test_todo_preset_tem_host_porta_e_seguranca_coerentes() -> None:
    for p in smtp.PRESETS:
        assert p.id and p.label
        assert p.security in {"starttls", "tls", "none"}
        assert 1 <= p.port <= 65535
        # Só o servidor próprio nasce sem host: os outros existem para preencher esse campo.
        assert p.host or p.id == "custom"


def test_os_provedores_principais_estao_no_catalogo() -> None:
    ids = {p.id for p in smtp.PRESETS}
    assert {"gmail", "microsoft365", "ses", "sendgrid", "custom"} <= ids


def test_presets_com_usuario_fixo_trazem_o_usuario() -> None:
    """SendGrid e Resend exigem um usuário literal, e errar isso parece senha errada."""
    assert smtp.POR_ID["sendgrid"].username == "apikey"
    assert smtp.POR_ID["resend"].username == "resend"


# --- envio --------------------------------------------------------------------------------


async def test_starttls_negocia_antes_de_autenticar(servidor: ServidorFalso) -> None:
    await smtp.enviar(conta(), "assunto", "corpo")
    assert servidor.starttls == 1
    assert servidor.logins == [("u", "p")]
    assert len(servidor.enviados) == 1


async def test_tls_direto_nao_chama_starttls(servidor: ServidorFalso) -> None:
    await smtp.enviar(conta(security="tls", port=465), "assunto", "corpo")
    assert servidor.starttls == 0
    assert servidor.ssl_direto is True


async def test_relay_sem_credencial_nao_tenta_autenticar(servidor: ServidorFalso) -> None:
    """Relay interno costuma aceitar sem login, e tentar autenticar quebra a entrega."""
    await smtp.enviar(conta(security="none", username="", password="", port=25), "a", "c")
    assert servidor.logins == []
    assert len(servidor.enviados) == 1


async def test_a_mensagem_leva_remetente_com_nome_e_destinatarios(servidor: ServidorFalso) -> None:
    await smtp.enviar(conta(destinatarios=["a@x.com", "b@x.com"]), "Assunto do alerta", "corpo")
    msg = servidor.enviados[0]
    assert msg["Subject"] == "Assunto do alerta"
    assert msg["From"] == "Lognix <lognix@exemplo.com>"
    assert msg["To"] == "a@x.com, b@x.com"


async def test_falta_de_configuracao_falha_antes_de_abrir_conexao(servidor: ServidorFalso) -> None:
    with pytest.raises(EnvioError, match="servidor SMTP"):
        await smtp.enviar(conta(host=""), "a", "c")
    with pytest.raises(EnvioError, match="destinatário"):
        await smtp.enviar(conta(destinatarios=[]), "a", "c")
    assert servidor.enviados == []


async def test_credencial_recusada_vira_erro_legivel(servidor: ServidorFalso) -> None:
    servidor.erro = smtplib.SMTPAuthenticationError(
        535, b"5.7.8 Username and Password not accepted"
    )
    with pytest.raises(EnvioError, match="recusou as credenciais"):
        await smtp.enviar(conta(), "a", "c")


async def test_servidor_inalcancavel_diz_host_e_porta(servidor: ServidorFalso) -> None:
    servidor.erro = OSError("Connection refused")
    with pytest.raises(EnvioError, match=r"smtp\.exemplo\.com:587"):
        await smtp.enviar(conta(), "a", "c")


# --- a regra ------------------------------------------------------------------------------


def test_severidade_minima_deixa_passar_o_que_e_mais_grave() -> None:
    assert alerts.passa("critical", "high") is True
    assert alerts.passa("high", "high") is True
    assert alerts.passa("medium", "high") is False
    assert alerts.passa("info", "info") is True


def test_severidade_desconhecida_nao_silencia_o_alerta() -> None:
    """Errar para mais é o lado certo: alerta a mais incomoda, alerta a menos esconde."""
    assert alerts.passa("inventada", "high") is True


# --- quando o insight nasce ---------------------------------------------------------------


@dataclass
class InsightFalso:
    id: str = "11111111-1111-1111-1111-111111111111"
    severity: str = "critical"
    title: str = "Banco inacessível"
    summary: str = "O serviço perdeu a conexão com o Postgres."
    probable_cause: str = "Postgres reiniciou."
    suggested_action: str = "Conferir o container do banco."
    confidence: float = 0.9


async def _ligar(authed: AsyncClient, **extras: Any) -> None:
    corpo = {
        "enabled": True,
        "host": "smtp.exemplo.com",
        "port": 587,
        "security": "starttls",
        "username": "u",
        "password": "p",
        "sender": "lognix@exemplo.com",
        "recipients": "ops@exemplo.com",
        **extras,
    }
    resp = await authed.put(ROTA, json=corpo)
    assert resp.status_code == 200, resp.text


@pytest.fixture
async def db():
    from lognix.db import get_sessionmaker

    async with get_sessionmaker()() as sessao:
        yield sessao


async def test_insight_grave_vira_email(authed: AsyncClient, db, servidor: ServidorFalso) -> None:
    await _ligar(authed)
    await alerts.avisar_do_insight(db, InsightFalso(), "api", "vm-01")
    assert len(servidor.enviados) == 1
    msg = servidor.enviados[0]
    assert msg["Subject"] == "[Lognix · critical] api: Banco inacessível"


async def test_o_email_nao_leva_linha_de_log(
    authed: AsyncClient, db, servidor: ServidorFalso
) -> None:
    """Caixa de e-mail é cópia que escapa do controle de acesso e fica para sempre."""
    await _ligar(authed)
    await alerts.avisar_do_insight(db, InsightFalso(), "api", "vm-01")
    corpo = servidor.enviados[0].get_content()
    assert "Postgres reiniciou." in corpo
    assert "/insights/11111111-1111-1111-1111-111111111111" in corpo
    assert "evidência" not in corpo.lower() or "estão em" in corpo


async def test_abaixo_da_severidade_minima_nao_manda(
    authed: AsyncClient, db, servidor: ServidorFalso
) -> None:
    await _ligar(authed, min_severity="critical")
    await alerts.avisar_do_insight(db, InsightFalso(severity="high"), "api", "vm-01")
    assert servidor.enviados == []


async def test_projeto_fora_da_lista_nao_manda(
    authed: AsyncClient, db, servidor: ServidorFalso
) -> None:
    await _ligar(authed, projects="checkout, worker")
    await alerts.avisar_do_insight(db, InsightFalso(), "api", "vm-01")
    assert servidor.enviados == []
    await alerts.avisar_do_insight(db, InsightFalso(), "checkout", "vm-01")
    assert len(servidor.enviados) == 1


async def test_canal_desligado_nao_manda(authed: AsyncClient, db, servidor: ServidorFalso) -> None:
    await _ligar(authed, enabled=False)
    await alerts.avisar_do_insight(db, InsightFalso(), "api", "vm-01")
    assert servidor.enviados == []


async def test_falha_de_envio_nao_sobe_para_o_ciclo(
    authed: AsyncClient, db, servidor: ServidorFalso
) -> None:
    """O insight já existe quando o e-mail é tentado: entrega não pode derrubar produção."""
    await _ligar(authed)
    servidor.erro = OSError("Connection refused")
    await alerts.avisar_do_insight(db, InsightFalso(), "api", "vm-01")  # não levanta

    from sqlalchemy import select

    from lognix.notifications.models import Notification, NotificationType

    linhas = (
        (
            await db.execute(
                select(Notification).where(Notification.type == NotificationType.email_failed)
            )
        )
        .scalars()
        .all()
    )
    assert len(linhas) == 1, "a falha tem que aparecer na tela"


async def test_host_caindo_manda_quando_a_regra_deixa(
    authed: AsyncClient, db, servidor: ServidorFalso
) -> None:
    await _ligar(authed)
    await alerts.avisar_host_caiu(db, "vm-01", "connection refused")
    assert servidor.enviados[0]["Subject"] == "[Lognix] Host vm-01 desconectado"

    servidor.enviados.clear()
    await _ligar(authed, on_host_down=False)
    await alerts.avisar_host_caiu(db, "vm-01", None)
    assert servidor.enviados == []


# --- rotas --------------------------------------------------------------------------------


async def test_rota_exige_login(client: AsyncClient) -> None:
    assert (await client.get(ROTA)).status_code == 401
    assert (await client.post(f"{ROTA}/test")).status_code == 401


async def test_estado_inicial_traz_os_presets_e_os_padroes(authed: AsyncClient) -> None:
    corpo = (await authed.get(ROTA)).json()
    assert corpo["enabled"] is False
    assert corpo["min_severity"] == "high"
    assert corpo["on_host_down"] is True
    assert corpo["has_password"] is False
    assert {p["id"] for p in corpo["presets"]} >= {"gmail", "ses", "custom"}


async def test_a_senha_nunca_volta_pela_api(authed: AsyncClient) -> None:
    await _ligar(authed)
    texto = (await authed.get(ROTA)).text
    assert "has_password" in texto
    assert '"p"' not in texto and 'password":"' not in texto


async def test_salvar_em_branco_mantem_a_senha_guardada(authed: AsyncClient) -> None:
    """Sem isto, mexer em qualquer outro campo apagaria a senha."""
    await _ligar(authed)
    await authed.put(ROTA, json={"password": "", "host": "outro.exemplo.com"})
    corpo = (await authed.get(ROTA)).json()
    assert corpo["has_password"] is True and corpo["host"] == "outro.exemplo.com"


async def test_recusa_severidade_e_seguranca_invalidas(authed: AsyncClient) -> None:
    assert (await authed.put(ROTA, json={"min_severity": "urgentissimo"})).status_code == 400
    assert (await authed.put(ROTA, json={"security": "sslzinho"})).status_code == 400


async def test_teste_de_envio_responde_o_erro_em_vez_de_estourar(
    authed: AsyncClient, servidor: ServidorFalso
) -> None:
    await _ligar(authed)
    servidor.erro = OSError("Connection refused")
    corpo = (await authed.post(f"{ROTA}/test")).json()
    assert corpo["ok"] is False and "Connection refused" in corpo["error"]


async def test_teste_de_envio_funciona(authed: AsyncClient, servidor: ServidorFalso) -> None:
    await _ligar(authed)
    corpo = (await authed.post(f"{ROTA}/test")).json()
    assert corpo["ok"] is True
    assert servidor.enviados[0]["Subject"] == "[Lognix] Teste de envio"
