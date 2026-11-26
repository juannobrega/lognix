#!/usr/bin/env python3
"""Monta o CHANGELOG a partir das tags e dos commits entre elas.

Escrito à mão, um changelog envelhece calado — igual à lista de endpoints que ficou quatro fases
para trás sem ninguém notar. Aqui ele é derivado do que foi realmente lançado, e portanto não tem
como discordar.

Uso: python scripts/gerar_changelog.py > .documentation/Software/CHANGELOG.md
"""

from __future__ import annotations

import re
import subprocess
import sys

IMAGEM = "ghcr.io/juannobrega/lognix"

#: Prefixo de commit convencional -> seção. O que não casa entra em "Outras mudanças"; o que é
#: ruído de manutenção fica fora, porque changelog é para quem usa, não para quem mantém.
SECOES = {
    "feat": "Novidades",
    "fix": "Correções",
    "perf": "Desempenho",
    "refactor": "Outras mudanças",
    "docs": "Outras mudanças",
}
IGNORAR = ("chore", "style", "test", "ci", "build")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout.strip()


def tags() -> list[str]:
    saida = git("tag", "--list", "v*", "--sort=-v:refname")
    return [t for t in saida.splitlines() if t]


def commits(de: str | None, ate: str) -> list[tuple[str, str]]:
    faixa = f"{de}..{ate}" if de else ate
    linhas = git("log", faixa, "--no-merges", "--pretty=%s").splitlines()
    saida: list[tuple[str, str]] = []
    for linha in linhas:
        m = re.match(r"^(\w+)(?:\([^)]*\))?!?:\s*(.+)$", linha)
        if not m:
            continue
        tipo, texto = m.group(1).lower(), m.group(2).strip()
        if tipo in IGNORAR:
            continue
        saida.append((SECOES.get(tipo, "Outras mudanças"), texto))
    return saida


def main() -> int:
    todas = tags()
    print("# Mudanças\n")
    if not todas:
        print("Nenhuma versão publicada ainda.")
        return 0

    print(
        "Gerado a partir das tags do repositório. As notas completas de cada versão, com os "
        f"commits, estão em [Releases](https://github.com/juannobrega/lognix/releases).\n"
    )

    for i, tag in enumerate(todas):
        anterior = todas[i + 1] if i + 1 < len(todas) else None
        data = git("log", "-1", "--format=%ad", "--date=short", tag)
        versao = tag.lstrip("v")
        print(f"## {tag} — {data}\n")
        print(f"```bash\ndocker pull {IMAGEM}:{versao}\n```\n")

        agrupado: dict[str, list[str]] = {}
        for secao, texto in commits(anterior, tag):
            agrupado.setdefault(secao, []).append(texto)
        if not agrupado:
            print("Sem mudanças visíveis para quem usa.\n")
            continue
        for secao in ("Novidades", "Correções", "Desempenho", "Outras mudanças"):
            if secao not in agrupado:
                continue
            print(f"### {secao}\n")
            for texto in agrupado[secao]:
                print(f"- {texto[0].upper()}{texto[1:]}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
