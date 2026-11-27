"""Daemon Docker falso para a autoatualização, por transporte. Ver ADR 019.

Separado do `fake_docker.py`, que serve um socket de verdade para o proxy somente leitura dos
hosts monitorados. Aqui o que interessa é a **sequência** da troca — parar, renomear, criar,
iniciar, esperar, remover — e o que acontece quando um passo falha no meio.
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class FakeDockerLocal:
    def __init__(
        self,
        *,
        saude: list[str] | None = None,
        falhar_em: str | None = None,
        sem_permissao: bool = False,
        auxiliar_rodando: bool = False,
    ) -> None:
        self.auxiliar_rodando = auxiliar_rodando
        #: Sequência de estados de saúde devolvidos a cada inspeção do contêiner novo.
        self.saude = saude or ["starting", "healthy"]
        #: Caminho que deve falhar, para testar o rollback. Ex.: "/containers/create".
        self.falhar_em = falhar_em
        self.sem_permissao = sem_permissao
        self.chamadas: list[tuple[str, str]] = []
        self.criados: list[dict[str, Any]] = []
        self.nomes: list[str] = []
        self.removidos: list[str] = []
        self.renomeados: list[tuple[str, str]] = []
        self.baixados: list[str] = []
        self.iniciados: list[str] = []
        self.parados: list[str] = []
        self._saude_lidas = 0

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._responder)

    def _proxima_saude(self) -> str:
        indice = min(self._saude_lidas, len(self.saude) - 1)
        self._saude_lidas += 1
        return self.saude[indice]

    def _responder(self, pedido: httpx.Request) -> httpx.Response:
        if self.sem_permissao:
            raise httpx.ConnectError("[Errno 13] Permission denied")
        caminho = pedido.url.path
        self.chamadas.append((pedido.method, caminho))
        if self.falhar_em and caminho.startswith(self.falhar_em):
            return httpx.Response(500, json={"message": "falha combinada no teste"})

        if caminho == "/_ping":
            return httpx.Response(200, text="OK", headers={"content-type": "text/plain"})
        if caminho == "/images/create":
            self.baixados.append(
                f"{pedido.url.params.get('fromImage')}:{pedido.url.params.get('tag')}"
            )
            return httpx.Response(
                200, text='{"status":"Downloaded"}', headers={"content-type": "text/plain"}
            )
        if caminho == "/containers/create":
            corpo = json.loads(pedido.content or b"{}")
            self.criados.append(corpo)
            nome = str(pedido.url.params.get("name"))
            self.nomes.append(nome)
            return httpx.Response(201, json={"Id": f"novo-{len(self.criados)}"})
        if caminho.startswith("/images/") and caminho.endswith("/json"):
            return httpx.Response(200, json={"Config": {"Cmd": ["lognix-entrypoint"]}})
        if caminho.endswith("/json") and caminho.startswith("/containers/"):
            alvo = caminho.split("/containers/")[1].rsplit("/json", 1)[0]
            if alvo.startswith("novo-"):
                saude = self._proxima_saude()
                return httpx.Response(
                    200,
                    json={
                        "Id": alvo,
                        "State": {
                            "Status": "exited" if saude in {"morto", "saiu-limpo"} else "running",
                            "Running": saude not in {"morto", "saiu-limpo"},
                            "ExitCode": 1 if saude == "morto" else 0,
                            "Health": {} if saude in {"sem", "saiu-limpo"} else {"Status": saude},
                        },
                    },
                )
            if alvo == "lognix-updater":
                return httpx.Response(
                    200,
                    json={
                        "Id": "aux",
                        "State": {
                            "Status": "running" if self.auxiliar_rodando else "exited",
                            "Running": self.auxiliar_rodando,
                            "ExitCode": 0,
                            "FinishedAt": "2026-11-27T18:00:00Z",
                        },
                    },
                )
            return httpx.Response(200, json=ANTIGO)
        if caminho.endswith("/start"):
            self.iniciados.append(caminho.split("/")[2])
            return httpx.Response(204)
        if caminho.endswith("/stop"):
            self.parados.append(caminho.split("/")[2])
            return httpx.Response(204)
        if caminho.endswith("/rename"):
            self.renomeados.append((caminho.split("/")[2], str(pedido.url.params.get("name"))))
            return httpx.Response(204)
        if caminho.endswith("/logs"):
            return httpx.Response(
                200, text="atualização concluída", headers={"content-type": "text/plain"}
            )
        if caminho.endswith("/connect"):
            return httpx.Response(200, json={})
        if pedido.method == "DELETE" and caminho.startswith("/containers/"):
            self.removidos.append(caminho.split("/containers/")[1])
            return httpx.Response(204)
        return httpx.Response(404, json={"message": f"não mapeado: {caminho}"})


#: Como o Docker descreve o contêiner do Lognix rodando por compose.
ANTIGO: dict[str, Any] = {
    "Id": "abc123def456",
    "Name": "/lognix-lognix-1",
    "Image": "sha256:imagem-antiga",
    "Config": {
        "Env": ["LOGNIX_SECRET_KEY=x" * 1, "DATABASE_URL=postgresql://..."],
        "Labels": {"com.docker.compose.project": "lognix"},
        "ExposedPorts": {"8000/tcp": {}},
        "Cmd": ["lognix-entrypoint"],
        "User": "",
        "WorkingDir": "/app",
    },
    "HostConfig": {
        "Binds": ["lognix_loki-data:/loki"],
        "NetworkMode": "lognix_default",
        "PortBindings": {"8000/tcp": [{"HostPort": "8080"}]},
        "RestartPolicy": {"Name": "unless-stopped"},
    },
    "NetworkSettings": {"Networks": {"lognix_default": {"Aliases": ["lognix"]}}},
}
