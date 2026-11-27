"""Autoatualização: capacidade, trava da versão, sequência da troca e rollback. Ver ADR 019."""

from __future__ import annotations

import shutil
import socket as rede
import tempfile
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient

from lognix.updates import docker as docker_local
from lognix.updates import service
from lognix.updates.docker import DockerError, DockerLocal
from lognix.updates.swap import trocar
from tests.fake_local_docker import FakeDockerLocal

ROTA = "/api/v1/system/update"


@pytest.fixture
def soquete() -> Iterator[str]:
    """Socket de verdade, só para `is_socket()` responder o que responderia em produção.

    Em /tmp, e não no tmp_path do pytest: no macOS o caminho dele estoura o limite do AF_UNIX.
    """
    pasta = tempfile.mkdtemp(prefix="lgx", dir="/tmp")
    caminho = str(Path(pasta) / "docker.sock")
    s = rede.socket(rede.AF_UNIX, rede.SOCK_STREAM)
    s.bind(caminho)
    try:
        yield caminho
    finally:
        s.close()
        shutil.rmtree(pasta, ignore_errors=True)


def instalar(falso: FakeDockerLocal) -> None:
    docker_local.set_fabrica(lambda caminho: DockerLocal(caminho, transport=falso.transport()))


@pytest.fixture(autouse=True)
def _limpar() -> Iterator[None]:
    service.limpar_cache()
    yield
    docker_local.set_fabrica(None)


async def sem_esperar(_segundos: float) -> None:
    """Espera injetada nos testes. Zerar o INTERVALO faria o contador do teto nunca andar, e
    trocar `asyncio.sleep` no processo inteiro mexeria com o laço da própria suíte."""
    return None


# --- capacidade ---------------------------------------------------------------------------


async def test_sem_socket_nao_pode(tmp_path: Path) -> None:
    quem = await service.capacidade(str(tmp_path / "nao-existe.sock"))
    assert quem.pode is False and quem.motivo == "socket_ausente"


async def test_arquivo_comum_no_lugar_do_socket_nao_pode(tmp_path: Path) -> None:
    arquivo = tmp_path / "docker.sock"
    arquivo.write_text("não sou um socket")
    quem = await service.capacidade(str(arquivo))
    assert quem.motivo == "socket_ausente"


async def test_socket_sem_permissao_tem_motivo_proprio(soquete: str) -> None:
    """Conserto diferente de socket ausente: falta `group_add`, não falta montar."""
    instalar(FakeDockerLocal(sem_permissao=True))
    quem = await service.capacidade(soquete)
    assert quem.pode is False and quem.motivo == "sem_permissao"


async def test_com_socket_e_docker_respondendo_pode(soquete: str) -> None:
    instalar(FakeDockerLocal())
    quem = await service.capacidade(soquete)
    assert quem.pode is True
    assert quem.container == "abc123def456"
    assert quem.nome == "lognix-lognix-1", "sem a barra que o Docker põe na frente"


# --- trava da versão ----------------------------------------------------------------------


def registro(tags: list[str]) -> httpx.MockTransport:
    def responder(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.path == "/token":
            return httpx.Response(200, json={"token": "t"})
        return httpx.Response(200, json={"tags": tags})

    return httpx.MockTransport(responder)


async def test_recusa_versao_que_nao_esta_no_registro(monkeypatch) -> None:
    """A referência da imagem nunca vem do pedido: sem essa trava, a rota é execução remota."""
    monkeypatch.setattr(service, "__version__", "1.0.0")
    with pytest.raises(ValueError, match="não está publicada"):
        await service.alvo_valido("9.9.9", transport=registro(["1.0.0", "1.1.0"]))


async def test_recusa_descer_de_versao(monkeypatch) -> None:
    monkeypatch.setattr(service, "__version__", "1.3.0")
    with pytest.raises(ValueError, match="não é mais nova"):
        await service.alvo_valido("1.1.0", transport=registro(["1.1.0", "1.3.0"]))


async def test_recusa_o_que_nao_e_versao(monkeypatch) -> None:
    monkeypatch.setattr(service, "__version__", "1.0.0")
    for lixo in ("latest", "../../evil", "1.2", "sha256:abc"):
        with pytest.raises(ValueError, match="versão inválida"):
            await service.alvo_valido(lixo, transport=registro(["1.1.0"]))


async def test_aceita_versao_publicada_e_mais_nova(monkeypatch) -> None:
    monkeypatch.setattr(service, "__version__", "1.3.0")
    assert await service.alvo_valido("1.4.0", transport=registro(["1.3.0", "1.4.0"])) == "1.4.0"


# --- disparo ------------------------------------------------------------------------------


async def test_baixa_antes_de_tocar_em_qualquer_coisa(soquete: str) -> None:
    falso = FakeDockerLocal()
    instalar(falso)
    await service.atualizar("1.4.0", socket=soquete)
    assert falso.baixados == ["ghcr.io/juannobrega/lognix:1.4.0"]
    # O pull vem antes de criar o auxiliar: se falhar, o mundo fica como estava.
    assert falso.chamadas.index(("POST", "/images/create")) < falso.chamadas.index(
        ("POST", "/containers/create")
    )


async def test_auxiliar_sobe_com_socket_sem_rede_e_como_root(soquete: str) -> None:
    falso = FakeDockerLocal()
    instalar(falso)
    await service.atualizar("1.4.0", socket=soquete)
    aux = falso.criados[-1]
    assert aux["Image"] == "ghcr.io/juannobrega/lognix:1.4.0", "o auxiliar roda a imagem nova"
    assert "lognix.updates.swap" in " ".join(aux["Cmd"])
    assert aux["HostConfig"]["Binds"] == [f"{soquete}:/var/run/docker.sock"]
    assert aux["HostConfig"]["NetworkMode"] == "none", "o trabalho é todo pelo socket"
    assert aux["User"] == "0:0", "precisa ser root para falar com o socket"
    assert falso.nomes[-1] == "lognix-updater"


async def test_auxiliar_anterior_sai_antes_do_novo(soquete: str) -> None:
    falso = FakeDockerLocal()
    instalar(falso)
    await service.atualizar("1.4.0", socket=soquete)
    assert "lognix-updater" in falso.removidos


async def test_pull_que_falha_nao_cria_auxiliar(soquete: str) -> None:
    falso = FakeDockerLocal(falhar_em="/images/create")
    instalar(falso)
    with pytest.raises(DockerError):
        await service.atualizar("1.4.0", socket=soquete)
    assert falso.criados == []


# --- a troca, e o rollback ----------------------------------------------------------------


async def test_troca_na_ordem_que_mantem_o_pior_caso_inofensivo(soquete: str) -> None:
    falso = FakeDockerLocal(saude=["starting", "healthy"])
    instalar(falso)
    assert (
        await trocar(
            espera=sem_esperar,
            container="abc123",
            nome="lognix-lognix-1",
            imagem="img:1.4.0",
            socket=soquete,
        )
        == 0
    )
    # Para, renomeia o antigo (não remove), cria, inicia, e só então descarta o antigo.
    assert falso.parados == ["abc123"]
    assert falso.renomeados == [("abc123", "lognix-lognix-1-antes-de-1.4.0")]
    assert falso.iniciados == ["novo-1"]
    # Pelo id: depois do rename, o nome de reserva é o que existe, mas o id é o que nunca muda.
    assert falso.removidos == ["abc123"]


async def test_o_novo_herda_a_especificacao_do_antigo(soquete: str) -> None:
    falso = FakeDockerLocal()
    instalar(falso)
    await trocar(
        espera=sem_esperar,
        container="abc123",
        nome="lognix-lognix-1",
        imagem="img:1.4.0",
        socket=soquete,
    )
    novo = falso.criados[0]
    assert novo["Image"] == "img:1.4.0"
    assert "DATABASE_URL=postgresql://..." in novo["Env"]
    assert novo["HostConfig"]["PortBindings"] == {"8000/tcp": [{"HostPort": "8080"}]}
    assert novo["HostConfig"]["RestartPolicy"] == {"Name": "unless-stopped"}
    assert novo["HostConfig"]["Binds"] == ["lognix_loki-data:/loki"]
    assert novo["Labels"]["com.docker.compose.project"] == "lognix"
    assert novo["NetworkingConfig"]["EndpointsConfig"]["lognix_default"]["Aliases"] == ["lognix"]


async def test_cmd_da_imagem_nao_e_congelado_no_novo(soquete: str) -> None:
    """Copiar o Cmd sempre prenderia o comando da versão velha numa imagem que mudou o seu."""
    falso = FakeDockerLocal()
    instalar(falso)
    await trocar(
        espera=sem_esperar,
        container="abc123",
        nome="lognix-lognix-1",
        imagem="img:1.4.0",
        socket=soquete,
    )
    assert "Cmd" not in falso.criados[0]


async def test_novo_que_nao_fica_saudavel_volta_para_o_antigo(soquete: str) -> None:
    falso = FakeDockerLocal(saude=["morto"])
    instalar(falso)
    assert (
        await trocar(
            espera=sem_esperar,
            container="abc123",
            nome="lognix-lognix-1",
            imagem="img:1.4.0",
            socket=soquete,
        )
        == 1
    )
    assert "novo-1" in falso.removidos, "o novo é descartado"
    assert ("abc123", "lognix-lognix-1") in falso.renomeados
    assert falso.iniciados[-1] == "abc123", "o antigo volta ao ar, pelo id"


async def test_criacao_que_falha_tambem_devolve_o_antigo(soquete: str) -> None:
    falso = FakeDockerLocal(falhar_em="/containers/create")
    instalar(falso)
    assert (
        await trocar(
            espera=sem_esperar,
            container="abc123",
            nome="lognix-lognix-1",
            imagem="img:1.4.0",
            socket=soquete,
        )
        == 1
    )
    assert ("abc123", "lognix-lognix-1") in falso.renomeados
    assert falso.iniciados == ["abc123"]


# --- rota ---------------------------------------------------------------------------------


async def test_aplicar_recusa_com_a_chave_desligada(authed: AsyncClient) -> None:
    resp = await authed.post(f"{ROTA}/apply", json={"version": "1.4.0"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "self_update_disabled"


async def test_aplicar_recusa_versao_invalida(authed: AsyncClient, monkeypatch) -> None:
    await authed.put(ROTA, json={"self_update_enabled": True})

    async def nao(versao: str, **kw: object) -> str:
        raise ValueError("a versão 9.9.9 não está publicada no registro")

    monkeypatch.setattr(service, "alvo_valido", nao)
    resp = await authed.post(f"{ROTA}/apply", json={"version": "9.9.9"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_version"


async def test_aplicar_sem_docker_explica_o_que_falta(authed: AsyncClient, monkeypatch) -> None:
    # A máquina de quem roda os testes pode ter Docker: o caminho é fixado para não depender.
    monkeypatch.setattr(docker_local, "SOCKET", "/tmp/lognix-nao-existe.sock")
    await authed.put(ROTA, json={"self_update_enabled": True})

    async def ok(versao: str, **kw: object) -> str:
        return versao

    monkeypatch.setattr(service, "alvo_valido", ok)
    resp = await authed.post(f"{ROTA}/apply", json={"version": "1.4.0"})
    assert resp.status_code == 409
    assert "não está montado" in resp.json()["error"]["message"]


async def test_estado_mostra_o_impedimento(authed: AsyncClient, monkeypatch) -> None:
    # Aponta para um socket que não existe: a máquina de quem roda os testes pode ter Docker,
    # e o teste não pode depender disso.
    monkeypatch.setattr(docker_local, "SOCKET", "/tmp/lognix-nao-existe.sock")
    await authed.put(ROTA, json={"self_update_enabled": True})
    corpo = (await authed.get(ROTA)).json()
    assert corpo["self_update_enabled"] is True
    assert corpo["can_self_update"] is False
    # Na suíte não há socket montado, que é exatamente o caso de quem não fez o opt-in.
    assert corpo["blocker"] == "socket_ausente"


async def test_estado_conta_a_ultima_tentativa(
    authed: AsyncClient, soquete: str, monkeypatch
) -> None:
    """É assim que o Lognix novo conta o fim de uma atualização que derrubou a tela."""
    instalar(FakeDockerLocal())
    monkeypatch.setattr(docker_local, "SOCKET", soquete)
    await authed.put(ROTA, json={"self_update_enabled": True})
    corpo = (await authed.get(ROTA)).json()
    assert corpo["can_self_update"] is True
    assert corpo["last_attempt"]["state"] == "exited"
    assert corpo["last_attempt"]["exit_code"] == 0
    assert "concluída" in corpo["last_attempt"]["log"]


async def test_imagem_sem_healthcheck_vale_30_segundos_de_pe(soquete: str) -> None:
    """Sem HEALTHCHECK não há sinal melhor que "não morreu"; o teto evita espera infinita."""
    falso = FakeDockerLocal(saude=["sem"])
    instalar(falso)
    assert (
        await trocar(
            espera=sem_esperar, container="abc", nome="lognix", imagem="img:1.4.0", socket=soquete
        )
        == 0
    )
    assert falso.removidos == ["abc"]


async def test_novo_que_nunca_fica_saudavel_estoura_o_teto_e_volta(
    soquete: str, monkeypatch
) -> None:
    from lognix.updates import swap

    # Teto baixo, intervalo intacto: zerar o INTERVALO faria `gasto` nunca andar, e o laço
    # rodaria para sempre. Aconteceu ao escrever este teste.
    monkeypatch.setattr(swap, "ESPERA_MAXIMA", 6)
    falso = FakeDockerLocal(saude=["starting"])
    instalar(falso)
    assert (
        await trocar(
            espera=sem_esperar, container="abc", nome="lognix", imagem="img:1.4.0", socket=soquete
        )
        == 1
    )
    assert ("abc", "lognix") in falso.renomeados


async def test_container_inexistente_nao_mexe_em_nada(soquete: str) -> None:
    from lognix.updates import swap

    falso = FakeDockerLocal(falhar_em="/containers/abc/json")
    instalar(falso)
    assert (
        await swap.trocar(
            espera=sem_esperar, container="abc", nome="lognix", imagem="img:1.4.0", socket=soquete
        )
        == 1
    )
    assert falso.parados == [] and falso.criados == []


async def test_as_opcoes_do_auxiliar_sao_as_que_ele_aceita(soquete: str) -> None:
    """O Lognix monta a linha de comando do auxiliar; opção renomeada num lado quebraria calada."""
    from lognix.updates import swap

    falso = FakeDockerLocal()
    instalar(falso)
    await service.atualizar("1.4.0", socket=soquete)
    cmd = falso.criados[-1]["Cmd"]
    assert cmd[:3] == ["python", "-m", "lognix.updates.swap"]
    args = swap.analisar(cmd[3:])
    assert args.container == "abc123def456"
    assert args.nome == "lognix-lognix-1"
    assert args.imagem == f"{service.IMAGEM}:1.4.0"


# --- o que o review de 2026-11-27 pegou ---------------------------------------------------


async def test_o_stream_do_pull_e_ndjson_e_nao_um_json_so(soquete: str) -> None:
    """O daemon devolve um objeto por linha com Content-Type application/json.

    Tratar como JSON único estoura com "Extra data", e toda atualização morria em 502 — o
    falso escondia isso devolvendo text/plain.
    """
    falso = FakeDockerLocal()
    instalar(falso)
    await service.atualizar("1.4.0", socket=soquete)
    assert falso.baixados == ["ghcr.io/juannobrega/lognix:1.4.0"]


async def test_erro_dentro_do_stream_do_pull_derruba_o_disparo(soquete: str) -> None:
    """Pull que falha volta HTTP 200 com o erro **dentro** de uma das linhas."""
    falso = FakeDockerLocal()
    instalar(falso)

    def com_erro(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.path == "/images/create":
            return httpx.Response(
                200,
                text='{"status":"Pulling"}\n{"error":"manifest unknown"}\n',
                headers={"content-type": "application/json"},
            )
        return falso._responder(pedido)

    docker_local.set_fabrica(
        lambda caminho: DockerLocal(caminho, transport=httpx.MockTransport(com_erro))
    )
    with pytest.raises(DockerError, match="manifest unknown"):
        await service.atualizar("1.4.0", socket=soquete)


async def test_o_rollback_opera_pelo_id_porque_o_nome_mudou(soquete: str) -> None:
    """Renomear não muda o id. Religar pelo nome antigo dá 404, e o Lognix nunca voltaria."""
    falso = FakeDockerLocal(saude=["morto"])
    instalar(falso)
    assert (
        await trocar(
            espera=sem_esperar,
            container="abc123",
            nome="lognix-lognix-1",
            imagem="img:1.4.0",
            socket=soquete,
        )
        == 1
    )
    assert falso.iniciados[-1] == "abc123", "o antigo volta pelo id, não pelo nome de reserva"
    assert ("abc123", "lognix-lognix-1") in falso.renomeados


async def test_contêiner_que_sai_com_zero_tambem_e_morte(soquete: str) -> None:
    """Sair com 0 não é sinal de saúde para quem deveria ficar de pé — e sem isso a espera
    consumia os 300 s inteiros com o Lognix fora do ar."""
    falso = FakeDockerLocal(saude=["saiu-limpo"])
    instalar(falso)
    assert (
        await trocar(
            espera=sem_esperar,
            container="abc123",
            nome="lognix",
            imagem="img:1.4.0",
            socket=soquete,
        )
        == 1
    )
    assert falso.iniciados[-1] == "abc123"


async def test_falha_ao_remover_o_antigo_nao_desfaz_uma_troca_que_deu_certo(soquete: str) -> None:
    falso = FakeDockerLocal()
    instalar(falso)

    def remocao_quebrada(pedido: httpx.Request) -> httpx.Response:
        if pedido.method == "DELETE":
            return httpx.Response(500, json={"message": "não deu"})
        return falso._responder(pedido)

    docker_local.set_fabrica(
        lambda caminho: DockerLocal(caminho, transport=httpx.MockTransport(remocao_quebrada))
    )
    codigo = await trocar(
        espera=sem_esperar,
        container="abc123",
        nome="lognix",
        imagem="img:1.4.0",
        socket=soquete,
    )
    assert codigo == 0, "o novo está saudável; antigo que não sai é sujeira, não motivo de volta"


async def test_nao_atropela_uma_troca_em_andamento(soquete: str) -> None:
    """Remover o auxiliar em execução mataria a sequência no meio, e sobraria um contêiner
    renomeado e parado sem ninguém para devolvê-lo."""
    falso = FakeDockerLocal(auxiliar_rodando=True)
    instalar(falso)
    with pytest.raises(RuntimeError, match="troca_em_andamento"):
        await service.atualizar("1.4.0", socket=soquete)
    assert falso.criados == []


async def test_404_ao_se_inspecionar_e_container_desconhecido(soquete: str) -> None:
    """Acontece com `hostname:` próprio ou `network_mode: host`, e o conserto é outro."""

    def sem_esse_container(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.path == "/_ping":
            return httpx.Response(200, text="OK", headers={"content-type": "text/plain"})
        return httpx.Response(404, json={"message": "no such container"})

    docker_local.set_fabrica(
        lambda caminho: DockerLocal(caminho, transport=httpx.MockTransport(sem_esse_container))
    )
    quem = await service.capacidade(soquete)
    assert quem.motivo == "container_desconhecido"


async def test_registro_inalcancavel_vira_502_e_nao_500(authed: AsyncClient, monkeypatch) -> None:
    await authed.put(ROTA, json={"self_update_enabled": True})

    async def sem_rede(versao: str, **kw: object) -> str:
        raise httpx.ConnectError("sem rota para o host")

    monkeypatch.setattr(service, "alvo_valido", sem_rede)
    resp = await authed.post(f"{ROTA}/apply", json={"version": "1.4.0"})
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "registry_unreachable"
