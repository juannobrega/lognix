"""Validação de um provider em etapas, como a dos hosts.

Testar e receber "falhou" é diferente de testar e saber **onde** falhou. Credencial recusada,
modelo que não existe, serviço fora do ar e preço não cadastrado são quatro problemas com quatro
soluções, e um booleano não distingue nenhum deles.

As etapas seguem a ordem em que as coisas podem dar errado, e param na primeira falha: não faz
sentido perguntar o preço de um modelo que o provedor diz não ter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from lognix.ai import registry
from lognix.ai.models import AiProviderConfig
from lognix.ai.provider import AiError
from lognix.ai.providers.base import SPECS

log = logging.getLogger(__name__)

Status = Literal["pending", "running", "ok", "failed"]


@dataclass
class Step:
    number: int
    name: str
    status: Status = "pending"
    message: str | None = None
    action: str | None = None
    detail: str | None = None


@dataclass
class Resultado:
    ok: bool
    steps: list[Step] = field(default_factory=list)


ETAPAS = (
    "Credenciais",
    "Serviço alcançável",
    "Modelo disponível",
    "Chamada de teste",
    "Preço para estimar custo",
)


async def validar(db: AsyncSession, provider: AiProviderConfig) -> Resultado:
    """Roda as etapas em ordem e para na primeira que falhar."""
    steps = [Step(n, nome) for n, nome in enumerate(ETAPAS, start=1)]
    spec = SPECS[provider.kind]  # type: ignore[index]

    def falha(i: int, msg: str, acao: str | None = None) -> Resultado:
        steps[i].status, steps[i].message, steps[i].action = "failed", msg, acao
        return Resultado(False, steps)

    # 1. Credenciais presentes e legíveis.
    credenciais = registry.read_credentials(provider)
    faltando = [c["label"] for c in spec.fields if c["required"] and not credenciais.get(c["key"])]
    if faltando:
        return falha(
            0,
            f"Falta preencher: {', '.join(faltando)}.",
            "Abra Editar credenciais e complete os campos.",
        )
    steps[0].status, steps[0].detail = "ok", f"{len(credenciais)} campo(s) guardado(s)"

    try:
        client = registry.open_provider(provider)
    except AiError as exc:
        return falha(0, exc.message)

    try:
        # 2 e 3. O catálogo prova as duas de uma vez: se ele responde, o serviço está de pé, e a
        # lista diz se o modelo existe. Quem não publica catálogo pula para a chamada de teste,
        # que é a prova real de qualquer jeito.
        if spec.has_catalog:
            try:
                catalogo = await client.models()
            except AiError as exc:
                return falha(1, exc.message, "Confira a credencial e o acesso à rede.")
            steps[1].status, steps[1].detail = "ok", f"{len(catalogo)} modelo(s) no catálogo"

            if not provider.default_model:
                return falha(2, "Nenhum modelo padrão escolhido.", "Escolha um em Modelos.")
            if catalogo and not any(m.id == provider.default_model for m in catalogo):
                return falha(
                    2,
                    f"O catálogo não lista '{provider.default_model}'.",
                    "Confira o identificador: ele precisa ser exatamente o do provedor.",
                )
            steps[2].status, steps[2].detail = "ok", provider.default_model
        else:
            steps[1].status = "ok"
            steps[1].detail = "este provedor não publica catálogo"
            if not provider.default_model:
                return falha(2, "Nenhum modelo padrão escolhido.", "Cadastre um em Modelos.")
            steps[2].status = "ok"
            steps[2].detail = f"{provider.default_model} (sem catálogo para conferir)"

        # 4. A prova real: uma chamada mínima, que também fica registrada em Consumo.
        ok, erro, resultado = await registry.test_provider(db, provider, provider.default_model)
        if not ok or resultado is None:
            return falha(3, erro or "O provedor recusou a chamada.")
        steps[3].status = "ok"
        steps[3].detail = f"respondeu em {resultado.latency_ms / 1000:.1f}s"
    finally:
        await client.aclose()

    # 5. Sem preço, o consumo aparece zerado — o que parece gratuito, não erro.
    preco = await registry.price_for(db, provider.id, provider.default_model or "")
    if resultado.cost_usd > 0:
        steps[4].status = "ok"
        steps[4].detail = "o provedor informa o custo em cada resposta"
    elif preco.prompt_usd_per_mtok or preco.completion_usd_per_mtok:
        steps[4].status = "ok"
        steps[4].detail = f"estimado por ${preco.prompt_usd_per_mtok or Decimal(0)}/Mtok"
    else:
        # Não é falha: o provedor funciona. Mas o gasto apareceria como zero.
        steps[4].status = "failed"
        steps[4].message = "Este provedor não informa custo e o modelo não tem preço cadastrado."
        steps[4].action = "Cadastre o preço em Modelos, senão o consumo aparecerá sempre zerado."
        return Resultado(True, steps)

    return Resultado(True, steps)
