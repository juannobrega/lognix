"""Contêiner auxiliar que troca a imagem do Lognix. Ver ADR 019.

Roda **a partir da imagem nova**, fora do contêiner do Lognix, porque um `stop` no próprio
contêiner mata o processo que o chamou no meio da operação.

A sequência é desenhada para que o pior caso seja "nada mudou", não "sem Lognix":

    renomeia o antigo → cria o novo → inicia → espera ficar saudável
                                                      ├── sim: remove o antigo
                                                      └── não: remove o novo, devolve o antigo

Os registros ficam no contêiner `lognix-updater`, que não é descartado: é por eles que o Lognix
novo conta na tela como terminou a atualização que derrubou a tela.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from lognix.updates.docker import DockerError, DockerLocal, abrir

#: Saudável leva o start-period (40 s) mais algumas rodadas do HEALTHCHECK. Migração longa de
#: banco cabe aqui; o teto existe para não esperar para sempre por um contêiner que morreu.
ESPERA_MAXIMA = 300
INTERVALO = 3


def diga(mensagem: str) -> None:
    print(f"{datetime.now(UTC).strftime('%H:%M:%S')} {mensagem}", flush=True)


def _config_do_novo(
    antigo: dict[str, Any], imagem_antiga: dict[str, Any], nova: str
) -> dict[str, Any]:
    """Especificação do contêiner novo, clonada do antigo.

    `Cmd` e `Entrypoint` só são copiados quando diferem dos da imagem antiga: copiar sempre
    congelaria o comando da versão velha numa imagem nova que mudou o seu.
    """
    cfg = antigo.get("Config") or {}
    da_imagem = (imagem_antiga.get("Config") or {}) if imagem_antiga else {}
    novo: dict[str, Any] = {
        "Image": nova,
        "Env": cfg.get("Env") or [],
        "Labels": cfg.get("Labels") or {},
        "ExposedPorts": cfg.get("ExposedPorts") or {},
        "User": cfg.get("User") or "",
        "WorkingDir": cfg.get("WorkingDir") or "",
        "Tty": bool(cfg.get("Tty")),
        "OpenStdin": bool(cfg.get("OpenStdin")),
        "HostConfig": antigo.get("HostConfig") or {},
    }
    for campo in ("Cmd", "Entrypoint"):
        atual = cfg.get(campo)
        if atual and atual != da_imagem.get(campo):
            novo[campo] = atual

    redes = ((antigo.get("NetworkSettings") or {}).get("Networks") or {}).items()
    # Só a primeira entra na criação; o Docker aceita uma rede por `create`. As outras entram
    # por `connect` depois, senão um contêiner em duas redes perderia a segunda.
    primeira = next(iter(redes), None)
    if primeira:
        nome, detalhe = primeira
        novo["NetworkingConfig"] = {
            "EndpointsConfig": {nome: {"Aliases": detalhe.get("Aliases") or []}}
        }
    return novo


async def _esperar_saudavel(
    docker: DockerLocal, alvo: str, espera: Callable[[float], Awaitable[None]] = asyncio.sleep
) -> bool:
    """True quando o contêiner fica saudável. False se morreu ou se o tempo acabou."""
    gasto = 0
    while gasto < ESPERA_MAXIMA:
        estado = (await docker.inspecionar(alvo)).get("State") or {}
        saude = (estado.get("Health") or {}).get("Status")
        # Parado é parado: sair com 0 não é sinal de saúde para quem deveria ficar de pé.
        if estado.get("Status") in {"exited", "dead"} or (
            not estado.get("Running") and estado.get("Status") != "created"
        ):
            diga(f"o contêiner novo parou com código {estado.get('ExitCode')}")
            return False
        if saude == "healthy":
            return True
        if saude is None and estado.get("Running") and gasto >= 30:
            # Imagem sem HEALTHCHECK: de pé por 30 s sem morrer é o melhor sinal que existe.
            diga("imagem sem HEALTHCHECK: aceito como no ar depois de 30 s de pé")
            return True
        await espera(INTERVALO)
        gasto += INTERVALO
    diga(f"o contêiner novo não ficou saudável em {ESPERA_MAXIMA} s")
    return False


async def trocar(
    *,
    container: str,
    nome: str,
    imagem: str,
    socket: str | None = None,
    espera: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> int:
    docker = abrir(socket)
    reserva = f"{nome}-antes-de-{imagem.rsplit(':', 1)[-1]}"
    try:
        antigo = await docker.inspecionar(container)
        if not antigo:
            diga(f"não achei o contêiner {container}")
            return 1
        imagem_antiga = {}
        try:
            imagem_antiga = await docker.inspecionar_imagem(antigo.get("Image") or "")
        except DockerError:
            # Imagem antiga removida do host: o clone segue sem a comparação de Cmd.
            diga("não consegui inspecionar a imagem antiga; copiando Cmd e Entrypoint como estão")
        config = _config_do_novo(antigo, imagem_antiga, imagem)

        diga(f"parando {nome}")
        await docker.parar(container)
        diga(f"renomeando o antigo para {reserva}")
        await docker.renomear(container, reserva)

        novo = ""
        try:
            diga(f"criando {nome} com {imagem}")
            novo = await docker.criar(nome, config)
            for rede, detalhe in list(
                ((antigo.get("NetworkSettings") or {}).get("Networks") or {}).items()
            )[1:]:
                await docker.conectar_rede(rede, novo, {"Aliases": detalhe.get("Aliases") or []})
            diga("iniciando")
            await docker.iniciar(novo)
            saudavel = await _esperar_saudavel(docker, novo, espera)
            if not saudavel:
                raise DockerError("o contêiner novo não subiu")
        except DockerError as exc:
            diga(f"falhou: {exc}")
            diga("desfazendo: removendo o novo e devolvendo o antigo")
            if novo:
                try:
                    await docker.remover(novo, forcar=True)
                except DockerError as erro:
                    diga(f"não consegui remover o novo: {erro}")
            # Pelo id, nunca pelo nome: renomear não muda o id, e o nome antigo já não existe.
            await docker.renomear(container, nome)
            await docker.iniciar(container)
            diga("o Lognix anterior está de volta no ar")
            return 1
        diga("no ar. removendo o contêiner antigo")
        try:
            await docker.remover(container, forcar=True)
        except DockerError as erro:
            # O novo está saudável: um antigo que não sai é sujeira, não motivo para desfazer.
            diga(f"o contêiner antigo ficou para trás, remova à mão: {erro}")
        diga(f"atualização concluída para {imagem}")
        return 0
    except DockerError as exc:
        diga(f"erro falando com o Docker: {exc}")
        return 1
    finally:
        await docker.aclose()


def analisar(argumentos: list[str] | None = None) -> argparse.Namespace:
    """Separado do `main` para o teste conferir, sem laço de eventos, que as opções que o
    `service.atualizar` monta no `Cmd` são as mesmas que este programa aceita."""
    analisador = argparse.ArgumentParser(prog="lognix.updates.swap")
    analisador.add_argument("--container", required=True, help="id do contêiner do Lognix")
    analisador.add_argument("--nome", required=True, help="nome que o contêiner novo recebe")
    analisador.add_argument("--imagem", required=True, help="referência completa da imagem nova")
    return analisador.parse_args(argumentos)


def main(argumentos: list[str] | None = None) -> int:
    args = analisar(argumentos)
    return asyncio.run(trocar(container=args.container, nome=args.nome, imagem=args.imagem))


if __name__ == "__main__":
    sys.exit(main())
