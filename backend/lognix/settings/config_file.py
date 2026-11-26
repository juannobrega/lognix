"""Configuração declarativa por arquivo. Ver ADR 014.

Três regras governam este módulo:

- **Ambiente ganha do arquivo**, que ganha do banco, que ganha do padrão. O ambiente vem por
  último na cadeia de quem escreve, então é quem um operador usa para corrigir uma instalação sem
  editar arquivo.
- **Segredo não se escreve aqui.** Qualquer valor aceita `${VAR}`, resolvido do ambiente na
  leitura. Variável faltando é erro de subida, não string vazia: um SMTP que sobe com senha em
  branco só falha no primeiro e-mail, longe da causa.
- **Arquivo inválido impede a subida**, dizendo onde. Configuração ignorada em silêncio é pior que
  configuração ausente, porque quem escreveu acredita que ela está valendo.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(Exception):
    """Erro no arquivo de configuração. Impede a subida de propósito."""


@dataclass(frozen=True)
class FileConfig:
    """O que o arquivo declarou, já com `${VAR}` resolvido."""

    #: Caminhos no formato "ai.enabled", para a interface saber o que desabilitar.
    managed: dict[str, Any] = field(default_factory=dict)
    providers: list[dict[str, Any]] = field(default_factory=list)
    path: Path | None = None

    def __bool__(self) -> bool:
        return bool(self.managed or self.providers)


def _resolve(value: Any, where: str) -> Any:
    """Troca `${VAR}` pelo ambiente. Recursivo, porque o arquivo é uma árvore."""
    if isinstance(value, dict):
        return {k: _resolve(v, f"{where}.{k}") for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, f"{where}[{i}]") for i, v in enumerate(value)]
    if not isinstance(value, str):
        return value

    faltando: list[str] = []

    def troca(m: re.Match[str]) -> str:
        nome = m.group(1)
        if nome not in os.environ:
            faltando.append(nome)
            return ""
        return os.environ[nome]

    resolvido = PLACEHOLDER.sub(troca, value)
    if faltando:
        raise ConfigError(
            f"{where}: a variável de ambiente {', '.join(faltando)} não está definida. "
            f"Ela é referenciada no arquivo de configuração e precisa existir antes da subida."
        )
    return resolvido


#: Chaves aceitas e como cada uma vira uma configuração do banco. Espelha o que a interface já
#: configura: nada pode ser configurável só pelo arquivo, senão vira recurso invisível na tela.
SETTING_KEYS: dict[str, str] = {
    "ai.enabled": "ai.enabled",
    "ai.max_input_tokens": "ai.max_input_tokens",
    "ai.max_output_tokens": "ai.max_output_tokens",
    "ai.concurrency": "ai.concurrency",
}


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for chave, valor in data.items():
        caminho = f"{prefix}.{chave}" if prefix else chave
        if isinstance(valor, dict):
            saida.update(_flatten(valor, caminho))
        else:
            saida[caminho] = valor
    return saida


def load(path: str | Path) -> FileConfig:
    """Lê o arquivo. Ausente devolve vazio; presente e inválido levanta."""
    arquivo = Path(path)
    if not arquivo.is_file():
        return FileConfig()

    try:
        bruto = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{arquivo}: YAML inválido. {exc}") from exc
    if not isinstance(bruto, dict):
        raise ConfigError(
            f"{arquivo}: a raiz precisa ser um mapa de chaves, não {type(bruto).__name__}."
        )

    bruto = _resolve(bruto, arquivo.name)
    providers = bruto.pop("providers", []) or []
    if not isinstance(providers, list):
        raise ConfigError(f"{arquivo}: 'providers' precisa ser uma lista.")
    for i, p in enumerate(providers):
        if not isinstance(p, dict):
            raise ConfigError(f"{arquivo}: providers[{i}] precisa ser um mapa.")
        if not p.get("kind"):
            raise ConfigError(f"{arquivo}: providers[{i}] não diz o 'kind'.")

    achatado = _flatten(bruto)
    desconhecidas = sorted(set(achatado) - set(SETTING_KEYS))
    if desconhecidas:
        raise ConfigError(
            f"{arquivo}: chave não reconhecida: {', '.join(desconhecidas)}. "
            f"Conhecidas: {', '.join(sorted(SETTING_KEYS))}, mais a lista 'providers'."
        )

    log.info(
        "configuração lida de %s: %d chave(s), %d provider(s)",
        arquivo,
        len(achatado),
        len(providers),
    )
    return FileConfig(managed=achatado, providers=providers, path=arquivo)


#: Configuração ativa desta instância. Lida uma vez na subida; a API consulta para saber
#: quais campos mostrar desabilitados.
_ativa = FileConfig()


def active() -> FileConfig:
    return _ativa


def is_managed(key: str) -> bool:
    """O valor veio do arquivo? Então a interface mostra, e não deixa editar."""
    return key in _ativa.managed


async def apply(db: Any, cfg: FileConfig) -> None:
    """Grava no banco o que o arquivo declarou, para o resto do código ler como sempre leu."""
    global _ativa
    from sqlalchemy import select

    from lognix.ai import registry
    from lognix.ai.models import AiProviderConfig
    from lognix.ai.providers.base import SPECS, ProviderKind
    from lognix.settings import service

    _ativa = cfg
    if not cfg:
        return

    for caminho, valor in cfg.managed.items():
        chave = SETTING_KEYS[caminho]
        texto = "true" if valor is True else "false" if valor is False else str(valor)
        await service.set_value(db, chave, texto)

    for item in cfg.providers:
        kind = str(item["kind"]).strip()
        try:
            kind_enum = ProviderKind(kind)
        except ValueError as exc:
            raise ConfigError(
                f"provider '{kind}' não existe. Conhecidos: {', '.join(sorted(ProviderKind))}."
            ) from exc

        nome = str(item.get("name") or SPECS[kind_enum].label).strip()
        existente = (
            await db.execute(select(AiProviderConfig).where(AiProviderConfig.name == nome))
        ).scalar_one_or_none()
        provider = existente or AiProviderConfig(kind=kind, name=nome)
        if existente is None:
            provider.priority = await registry.next_priority(db)
            db.add(provider)
            await db.flush()

        provider.kind = kind
        if item.get("default_model"):
            modelo = str(item["default_model"]).strip()
            provider.default_model = modelo
            await registry.ensure_model(db, provider, modelo, label=modelo)
        credenciais = item.get("credentials") or {}
        if credenciais:
            registry.store_credentials(provider, {k: str(v) for k, v in credenciais.items()})
        provider.enabled = bool(item.get("enabled", True)) and bool(
            provider.credentials_enc and provider.default_model
        )

    await db.commit()
    log.info(
        "configuração aplicada: %d chave(s), %d provider(s)", len(cfg.managed), len(cfg.providers)
    )
