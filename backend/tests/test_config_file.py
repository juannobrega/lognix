"""Arquivo de configuração: ADR 014.

Este módulo derruba a subida quando o arquivo está errado, então errar aqui deixa a instalação
inteira fora do ar. Os casos abaixo cobrem as três regras: resolver segredo do ambiente, recusar o
que não dá para honrar, e não inventar significado para o que não entende.
"""

from __future__ import annotations

import pytest

from lognix.settings.config_file import ConfigError, load


def escreve(tmp_path, texto: str):
    arquivo = tmp_path / "config.yaml"
    arquivo.write_text(texto, encoding="utf-8")
    return arquivo


def test_arquivo_ausente_nao_e_erro(tmp_path) -> None:
    """Instalação sem arquivo é o caso comum: nada muda."""
    cfg = load(tmp_path / "nao-existe.yaml")
    assert not cfg and cfg.managed == {} and cfg.providers == []


def test_le_chaves_conhecidas_achatando_a_arvore(tmp_path) -> None:
    cfg = load(escreve(tmp_path, "ai:\n  enabled: true\n  concurrency: 5\n"))
    assert cfg.managed == {"ai.enabled": True, "ai.concurrency": 5}
    assert bool(cfg) is True


def test_interruptor_do_mcp_entra_pelo_arquivo(tmp_path) -> None:
    """Quem sobe a instalação por arquivo precisa poder deixar o MCP ligado de saída."""
    cfg = load(escreve(tmp_path, "mcp:\n  enabled: true\n"))
    assert cfg.managed == {"mcp.enabled": True}


def test_exemplo_versionado_e_valido(monkeypatch) -> None:
    """O arquivo que a documentação manda copiar não pode ser recusado na subida."""
    from pathlib import Path

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-teste")
    exemplo = Path(__file__).resolve().parents[2] / "config" / "config.yaml.example"
    cfg = load(exemplo)
    assert "mcp.enabled" in cfg.managed
    assert cfg.providers


def test_variavel_de_ambiente_entra_no_lugar_do_segredo(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MINHA_CHAVE", "sk-secreta")
    cfg = load(
        escreve(
            tmp_path,
            "providers:\n  - kind: openai\n    default_model: gpt-5\n"
            "    credentials:\n      api_key: ${MINHA_CHAVE}\n",
        )
    )
    assert cfg.providers[0]["credentials"]["api_key"] == "sk-secreta"


def test_variavel_faltando_derruba_a_subida(tmp_path, monkeypatch) -> None:
    """Resolver para string vazia faria o SMTP falhar no primeiro e-mail, longe da causa."""
    monkeypatch.delenv("NAO_DEFINIDA", raising=False)
    with pytest.raises(ConfigError, match="NAO_DEFINIDA"):
        load(
            escreve(
                tmp_path,
                "providers:\n  - kind: openai\n    credentials:\n      api_key: ${NAO_DEFINIDA}\n",
            )
        )


def test_chave_desconhecida_e_recusada_dizendo_quais_existem(tmp_path) -> None:
    """Chave ignorada em silêncio é pior: quem escreveu acredita que ela está valendo."""
    with pytest.raises(ConfigError) as erro:
        load(escreve(tmp_path, "ai:\n  enabled: true\nsmtp:\n  host: exemplo\n"))
    assert "smtp.host" in str(erro.value)
    assert "ai.enabled" in str(erro.value), "o erro precisa dizer quais chaves existem"


def test_yaml_quebrado_diz_que_e_o_yaml(tmp_path) -> None:
    with pytest.raises(ConfigError, match="YAML inválido"):
        load(escreve(tmp_path, "ai:\n  enabled: [sem fechar\n"))


def test_raiz_que_nao_e_mapa_e_recusada(tmp_path) -> None:
    with pytest.raises(ConfigError, match="mapa de chaves"):
        load(escreve(tmp_path, "- isto\n- e uma lista\n"))


def test_provider_sem_kind_e_recusado(tmp_path) -> None:
    with pytest.raises(ConfigError, match="kind"):
        load(escreve(tmp_path, "providers:\n  - name: sem tipo\n"))


def test_providers_precisa_ser_lista(tmp_path) -> None:
    with pytest.raises(ConfigError, match="lista"):
        load(escreve(tmp_path, "providers:\n  kind: openai\n"))
