"""Cliente do Docker **local**, para a autoatualização. Ver ADR 019.

Este é o único lugar do Lognix que escreve no Docker, e escreve no socket da máquina onde o
próprio Lognix roda — nunca num host monitorado. A garantia de somente-leitura dos hosts
monitorados vive em `lognix/docker/client.py`, que não tem nenhum método de escrita e continua
sendo o único caminho até eles. Os dois arquivos são separados para que essa fronteira seja
visível em vez de combinada.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

SOCKET = "/var/run/docker.sock"
#: Nome fixo do auxiliar. Fixo para dar `docker logs lognix-updater` a quem precisar.
AUXILIAR = "lognix-updater"


class DockerError(Exception):
    def __init__(self, mensagem: str, status: int | None = None) -> None:
        super().__init__(mensagem)
        self.status = status


class SemPermissaoError(DockerError):
    """Socket montado e inalcançável: processo fora do grupo `docker`. Pede `group_add`."""


class DockerLocal:
    def __init__(
        self,
        socket: str = SOCKET,
        *,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.socket = socket
        self._cliente = httpx.AsyncClient(
            transport=transport or httpx.AsyncHTTPTransport(uds=socket),
            base_url="http://docker",
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._cliente.aclose()

    async def _pedir(self, metodo: str, caminho: str, cru: bool = False, **kw: Any) -> Any:
        try:
            resposta = await self._cliente.request(metodo, caminho, **kw)
        except httpx.HTTPError as exc:
            # EACCES chega como erro de conexão: o socket existe e recusa quem não é do grupo.
            if "Permission denied" in str(exc):
                raise SemPermissaoError(
                    "O socket do Docker existe, mas este processo não tem permissão para usá-lo."
                ) from exc
            raise DockerError(f"Docker não respondeu: {exc}") from exc
        if resposta.status_code >= 400:
            raise DockerError(
                f"Docker respondeu HTTP {resposta.status_code}: {resposta.text[:300]}",
                resposta.status_code,
            )
        # `cru` existe para o stream do pull: ele chega com Content-Type application/json e um
        # objeto JSON **por linha**, então `resposta.json()` estoura com "Extra data".
        if not cru and resposta.headers.get("content-type", "").startswith("application/json"):
            return resposta.json()
        return resposta.text

    async def ping(self) -> bool:
        return bool(await self._pedir("GET", "/_ping") == "OK")

    async def inspecionar(self, alvo: str) -> dict[str, Any]:
        dados = await self._pedir("GET", f"/containers/{alvo}/json")
        return dados if isinstance(dados, dict) else {}

    async def inspecionar_imagem(self, referencia: str) -> dict[str, Any]:
        dados = await self._pedir("GET", f"/images/{referencia}/json")
        return dados if isinstance(dados, dict) else {}

    async def baixar(self, imagem: str, tag: str) -> None:
        """`pull`. Quem baixa é o daemon; esta chamada só espera e falha alto se der errado."""
        resposta = await self._pedir(
            "POST",
            "/images/create",
            cru=True,
            params={"fromImage": imagem, "tag": tag},
            timeout=httpx.Timeout(30.0, read=900.0),
        )
        # O stream do pull devolve um JSON por linha, e erro vem *dentro* de uma delas com 200.
        for linha in str(resposta).splitlines():
            linha = linha.strip()
            if not linha:
                continue
            try:
                evento = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if evento.get("error"):
                raise DockerError(f"falha ao baixar {imagem}:{tag}: {evento['error']}")

    async def criar(self, nome: str, config: dict[str, Any]) -> str:
        dados = await self._pedir("POST", "/containers/create", params={"name": nome}, json=config)
        identificador = (dados or {}).get("Id")
        if not identificador:
            raise DockerError("o Docker criou o contêiner e não devolveu o id")
        return str(identificador)

    async def iniciar(self, alvo: str) -> None:
        await self._pedir("POST", f"/containers/{alvo}/start")

    async def parar(self, alvo: str, *, segundos: int = 30) -> None:
        await self._pedir(
            "POST",
            f"/containers/{alvo}/stop",
            params={"t": segundos},
            timeout=httpx.Timeout(30.0, read=segundos + 30),
        )

    async def renomear(self, alvo: str, nome: str) -> None:
        await self._pedir("POST", f"/containers/{alvo}/rename", params={"name": nome})

    async def remover(self, alvo: str, *, forcar: bool = False) -> None:
        await self._pedir(
            "DELETE", f"/containers/{alvo}", params={"force": "true" if forcar else "false"}
        )

    async def conectar_rede(self, rede: str, alvo: str, config: dict[str, Any]) -> None:
        await self._pedir(
            "POST", f"/networks/{rede}/connect", json={"Container": alvo, "EndpointConfig": config}
        )

    async def registros(self, alvo: str, *, linhas: int = 60) -> str:
        """Criamos o auxiliar com Tty, então os registros voltam como texto, sem multiplexação."""
        dados = await self._pedir(
            "GET",
            f"/containers/{alvo}/logs",
            cru=True,
            params={"stdout": "true", "stderr": "true", "tail": str(linhas)},
        )
        return str(dados)


#: Como o resto do código abre o Docker local. Trocável nos testes, como o gerenciador do Alloy
#: e o supervisor de túneis: ninguém deveria precisar de um daemon de verdade para testar a
#: sequência da troca.
_fabrica: Callable[[str], DockerLocal] = DockerLocal


def abrir(socket: str | None = None) -> DockerLocal:
    return _fabrica(socket or SOCKET)


def set_fabrica(fabrica: Callable[[str], DockerLocal] | None) -> None:
    global _fabrica
    _fabrica = fabrica or DockerLocal
