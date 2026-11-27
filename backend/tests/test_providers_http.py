"""Os clientes de provider contra um transporte falso.

Esta camada estava entre 0% e 22% de cobertura, e é a que gasta dinheiro: ela monta o corpo da
requisição, lê tokens e custo da resposta, e decide o que é erro de credencial, de modelo, de
limite ou de rede. Cada uma dessas decisões muda o que o usuário vê e se a cadeia desce para o
próximo provider.

Tudo aqui usa `httpx.MockTransport`: nenhum teste fala com serviço real.
"""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest

from lognix.ai.models import CostSource
from lognix.ai.provider import AiError, RateLimitedError
from lognix.ai.providers.anthropic import AnthropicProvider
from lognix.ai.providers.bedrock import BedrockProvider
from lognix.ai.providers.openai import OpenAiProvider
from lognix.ai.providers.openrouter import OpenRouterProvider

ESQUEMA = {"type": "object", "properties": {"x": {"type": "string"}}}


def transporte(resposta, registro: list[httpx.Request] | None = None) -> httpx.MockTransport:
    def responde(req: httpx.Request) -> httpx.Response:
        if registro is not None:
            registro.append(req)
        return resposta(req) if callable(resposta) else resposta

    return httpx.MockTransport(responde)


def resposta_chat(conteudo: str = "ok", **extra) -> httpx.Response:
    corpo = {
        "id": "gen-1",
        "model": "m",
        "choices": [{"message": {"content": conteudo}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30, **extra},
    }
    return httpx.Response(200, json=corpo)


class TestAnthropic:
    """Protocolo próprio: /v1/messages, x-api-key, system como campo de primeira classe."""

    async def test_monta_o_corpo_no_formato_da_anthropic(self) -> None:
        reqs: list[httpx.Request] = []
        resp = httpx.Response(
            200,
            json={
                "id": "msg_1",
                "model": "claude-haiku-5-5",
                "content": [{"type": "text", "text": "resposta"}],
                "usage": {"input_tokens": 90, "output_tokens": 12},
                "stop_reason": "end_turn",
            },
        )
        p = AnthropicProvider("sk-ant-x", transport=transporte(resp, reqs))
        r = await p.complete(
            system="seja breve",
            user="o que houve?",
            schema=None,
            model="claude-haiku-5-5",
            max_output_tokens=100,
        )
        await p.aclose()

        corpo = json.loads(reqs[0].content)
        assert reqs[0].url.path == "/v1/messages"
        assert reqs[0].headers["x-api-key"] == "sk-ant-x"
        assert reqs[0].headers["anthropic-version"]
        assert corpo["system"] == "seja breve"
        assert corpo["messages"][0]["content"][0]["text"] == "o que houve?"
        assert "temperature" not in corpo, "os modelos novos recusam temperature com HTTP 400"
        assert r.text == "resposta" and r.input_tokens == 90 and r.output_tokens == 12
        assert r.cost_source == CostSource.unknown, "a Anthropic não informa custo"

    async def test_esquema_vai_no_prompt_porque_nao_ha_response_format(self) -> None:
        reqs: list[httpx.Request] = []
        resp = httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "{}"}], "usage": {}, "model": "m"},
        )
        p = AnthropicProvider("k", transport=transporte(resp, reqs))
        await p.complete(system="s", user="u", schema=ESQUEMA, model="m", max_output_tokens=10)
        await p.aclose()
        assert "esquema" in json.loads(reqs[0].content)["system"].lower()

    async def test_conteudo_vazio_e_erro_e_nao_resposta_boa(self) -> None:
        resp = httpx.Response(200, json={"content": [], "usage": {}, "stop_reason": "max_tokens"})
        p = AnthropicProvider("k", transport=transporte(resp))
        with pytest.raises(AiError, match="vazio"):
            await p.complete(system="s", user="u", schema=None, model="m", max_output_tokens=10)
        await p.aclose()

    @pytest.mark.parametrize(
        ("status", "trecho"),
        [(401, "chave"), (403, "chave"), (404, "Modelo não encontrado")],
    )
    async def test_erros_dizem_o_que_fazer(self, status: int, trecho: str) -> None:
        p = AnthropicProvider("k", transport=transporte(httpx.Response(status, json={})))
        with pytest.raises(AiError, match=trecho):
            await p.complete(system="s", user="u", schema=None, model="m", max_output_tokens=10)
        await p.aclose()

    async def test_limite_de_uso_e_retryable_e_nao_erro_comum(self) -> None:
        resp = httpx.Response(429, headers={"retry-after": "30"}, json={})
        p = AnthropicProvider("k", transport=transporte(resp))
        with pytest.raises(RateLimitedError) as erro:
            await p.complete(system="s", user="u", schema=None, model="m", max_output_tokens=10)
        await p.aclose()
        assert erro.value.retryable

    async def test_lista_modelos_com_nome_de_exibicao(self) -> None:
        resp = httpx.Response(
            200,
            json={"data": [{"id": "claude-haiku-5-5", "display_name": "Claude Haiku 5.5"}]},
        )
        p = AnthropicProvider("k", transport=transporte(resp))
        modelos = await p.models()
        await p.aclose()
        assert modelos[0].id == "claude-haiku-5-5" and "Haiku" in modelos[0].name


class TestOpenAiCompativel:
    """A mesma classe serve Groq, Mistral, DeepSeek e companhia: muda a URL e o nome."""

    async def test_usa_a_url_base_e_o_nome_do_provedor_nos_erros(self) -> None:
        reqs: list[httpx.Request] = []
        p = OpenAiProvider(
            "k",
            base_url="https://api.groq.com/openai/v1",
            kind="groq",
            name="Groq",
            transport=transporte(httpx.Response(401, json={}), reqs),
        )
        with pytest.raises(AiError, match="Groq"):
            await p.complete(system="s", user="u", schema=None, model="m", max_output_tokens=10)
        await p.aclose()
        assert reqs[0].url.host == "api.groq.com"

    async def test_esquema_vira_response_format(self) -> None:
        reqs: list[httpx.Request] = []
        p = OpenAiProvider("k", transport=transporte(resposta_chat(), reqs))
        await p.complete(system="s", user="u", schema=ESQUEMA, model="m", max_output_tokens=10)
        await p.aclose()
        corpo = json.loads(reqs[0].content)
        assert corpo["response_format"]["json_schema"]["strict"] is True

    async def test_organizacao_entra_no_cabecalho(self) -> None:
        reqs: list[httpx.Request] = []
        p = OpenAiProvider("k", organization="org-x", transport=transporte(resposta_chat(), reqs))
        await p.test("m")
        await p.aclose()
        assert reqs[0].headers["OpenAI-Organization"] == "org-x"

    async def test_sem_chave_nao_manda_cabecalho_de_autorizacao(self) -> None:
        """O Ollama roda local e não exige credencial; mandar `Bearer ` vazio é pedir 401."""
        reqs: list[httpx.Request] = []
        p = OpenAiProvider(
            "", base_url="http://ollama:11434/v1", transport=transporte(resposta_chat(), reqs)
        )
        await p.test("llama")
        await p.aclose()
        assert "authorization" not in {k.lower() for k in reqs[0].headers}

    async def test_erro_5xx_e_retentado_e_depois_desiste(self) -> None:
        tentativas = {"n": 0}

        def responde(_req: httpx.Request) -> httpx.Response:
            tentativas["n"] += 1
            return httpx.Response(503, json={})

        p = OpenAiProvider("k", transport=transporte(responde))
        with pytest.raises(AiError) as erro:
            await p.complete(system="s", user="u", schema=None, model="m", max_output_tokens=10)
        await p.aclose()
        assert tentativas["n"] == 3, "duas tentativas extras, como o cliente promete"
        assert erro.value.retryable

    async def test_falha_de_rede_tambem_e_retentada(self) -> None:
        tentativas = {"n": 0}

        def responde(_req: httpx.Request) -> httpx.Response:
            tentativas["n"] += 1
            raise httpx.ConnectError("sem rota")

        p = OpenAiProvider("k", transport=transporte(responde))
        with pytest.raises(AiError, match="rede"):
            await p.test("m")
        await p.aclose()
        assert tentativas["n"] == 3

    async def test_lista_modelos(self) -> None:
        resp = httpx.Response(200, json={"data": [{"id": "b"}, {"id": "a"}]})
        p = OpenAiProvider("k", transport=transporte(resp))
        modelos = await p.models()
        await p.aclose()
        assert [m.id for m in modelos] == ["a", "b"], "ordenados, para a busca ficar previsível"


class TestOpenRouter:
    async def test_pede_o_custo_na_resposta_e_o_usa(self) -> None:
        def responde(req: httpx.Request) -> httpx.Response:
            if req.method == "POST":
                return resposta_chat(cost=0.0042)
            return httpx.Response(200, json={"data": {"total_cost": 0.0042}})

        p = OpenRouterProvider("sk-or-x", transport=transporte(responde))
        r = await p.complete(system="s", user="u", schema=None, model="m", max_output_tokens=10)
        await p.aclose()
        assert r.cost_source == CostSource.provider
        assert r.cost_usd == Decimal("0.0042")

    async def test_identifica_o_lognix_nos_cabecalhos(self) -> None:
        reqs: list[httpx.Request] = []

        def responde(req: httpx.Request) -> httpx.Response:
            reqs.append(req)
            return (
                resposta_chat() if req.method == "POST" else httpx.Response(200, json={"data": {}})
            )

        p = OpenRouterProvider("k", transport=transporte(responde))
        await p.test("m")
        await p.aclose()
        nomes = {k.lower() for k in reqs[0].headers}
        assert "http-referer" in nomes and "x-title" in nomes


class TestBedrock:
    """Converse API com assinatura SigV4, sem boto3."""

    async def test_assina_a_requisicao_e_usa_a_converse(self) -> None:
        reqs: list[httpx.Request] = []
        resp = httpx.Response(
            200,
            json={
                "output": {"message": {"content": [{"text": "oi"}]}},
                "usage": {"inputTokens": 50, "outputTokens": 7},
                "stopReason": "end_turn",
            },
        )
        p = BedrockProvider(
            region="us-east-1",
            access_key_id="AKIA",
            secret_access_key="s",
            transport=transporte(resp, reqs),
        )
        r = await p.complete(
            system="s", user="u", schema=None, model="anthropic.x", max_output_tokens=10
        )
        await p.aclose()

        assert reqs[0].url.path.endswith("/model/anthropic.x/converse")
        assert "bedrock-runtime.us-east-1" in reqs[0].url.host
        auth = reqs[0].headers["authorization"]
        assert auth.startswith("AWS4-HMAC-SHA256") and "us-east-1" in auth
        corpo = json.loads(reqs[0].content)
        assert "temperature" not in corpo["inferenceConfig"]
        assert r.input_tokens == 50 and r.cost_source == CostSource.unknown

    async def test_credencial_temporaria_entra_na_assinatura(self) -> None:
        reqs: list[httpx.Request] = []
        resp = httpx.Response(
            200, json={"output": {"message": {"content": [{"text": "x"}]}}, "usage": {}}
        )
        p = BedrockProvider(
            region="us-east-1",
            access_key_id="AKIA",
            secret_access_key="s",
            session_token="tok",
            transport=transporte(resp, reqs),
        )
        await p.test("m")
        await p.aclose()
        assert reqs[0].headers["x-amz-security-token"] == "tok"

    async def test_403_fala_de_permissao_iam(self) -> None:
        p = BedrockProvider(
            region="us-east-1",
            access_key_id="A",
            secret_access_key="s",
            transport=transporte(httpx.Response(403, json={})),
        )
        with pytest.raises(AiError, match="InvokeModel"):
            await p.test("m")
        await p.aclose()

    async def test_lista_so_modelos_de_texto(self) -> None:
        resp = httpx.Response(
            200,
            json={
                "modelSummaries": [
                    {
                        "modelId": "txt",
                        "inputModalities": ["TEXT"],
                        "outputModalities": ["TEXT"],
                        "providerName": "Anthropic",
                        "modelName": "Claude",
                    },
                    {
                        "modelId": "img",
                        "inputModalities": ["TEXT"],
                        "outputModalities": ["IMAGE"],
                        "providerName": "X",
                        "modelName": "Y",
                    },
                ]
            },
        )
        p = BedrockProvider(
            region="us-east-1", access_key_id="A", secret_access_key="s", transport=transporte(resp)
        )
        modelos = await p.models()
        await p.aclose()
        assert [m.id for m in modelos] == ["txt"], "modelo de imagem não serve para explicar log"
