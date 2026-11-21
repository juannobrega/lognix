# CI/CD

**Status:** Em revisão · **Atualizado:** 2026-11-21

## 1. Modelo de branches

```
dev  ──PR──►  main  ──merge──►  tag vX.Y.Z  ──►  GitHub Release
```

- `dev` é a branch de trabalho. Todo desenvolvimento acontece nela ou em branches curtas que voltam para ela.
- `main` só recebe pull requests vindos de `dev`. Nunca commit direto.
- Cada merge em `main` com label de release gera tag e release automaticamente.
- O release, por ora, é **apenas o código**: tag, notas geradas e o repositório. Imagens Docker publicadas ficam no roadmap.

## 2. Workflow de release

Arquivo: `.github/workflows/release.yml`. Conteúdo definido pelo dono do projeto em 2026-11-21 e guardado
verbatim em [Release Workflow.yml](Release%20Workflow.yml). Resumo do comportamento:

| Aspecto | Regra |
|---|---|
| Gatilho | pull request **fechado** em `main`, e só age se foi **merged** |
| Tamanho do bump | exatamente **uma** label no PR: `release:major`, `release:minor` ou `release:patch` |
| Sem label | o workflow **falha** de propósito. Nada é adivinhado |
| Mais de uma label | falha |
| `release:skip` | merge sem release, job pulado, não falhado |
| Recuperação | adicionar a label ao PR já mergeado e reexecutar o workflow pela aba Actions |
| Concorrência | grupo `release-main`, sem cancelamento: dois merges não disputam o mesmo número |
| Versão | lê a maior tag `v*`, incrementa conforme a label. Sem tags, parte de `0.0.0` |
| Fonte de verdade | escreve a versão em `pyproject.toml`, commita em `main` com `Release vX.Y.Z`, cria tag anotada, publica release com notas geradas |
| Tag existente | falha, para detectar release manual ou corrida |

## 3. Pontos que o monorepo precisa respeitar

O workflow altera `pyproject.toml` **na raiz** do repositório. Isso impõe:

1. **Decidido em 2026-11-21:** backend em `backend/`, frontend em `frontend/`, e um `pyproject.toml`
   **mínimo na raiz** que é a fonte da versão. Ver Backend/Estrutura do Projeto.
2. O workflow passa a atualizar também `frontend/package.json`, no mesmo passo de versão. O arquivo
   guardado em Release Workflow.yml precisa desse ajuste ao ser copiado para `.github/workflows/`.
   O passo "Set the version" ganha a escrita no `package.json` e o `git add` inclui os dois arquivos.
3. A versão aparece na interface, no rodapé, e na resposta de `GET /api/health`, lida do pacote
   instalado. Permite saber qual release está rodando.

## 4. Labels de release por fase

| Situação | Label |
|---|---|
| Fase concluída antes do 1.0.0, ex.: 0.3.0 → 0.4.0 | `release:minor` |
| Correção dentro de uma fase | `release:patch` |
| Mudança só de documentação em `.documentation/` | `release:skip` |
| Passagem para 1.0.0 | `release:major` a partir de 0.9.x |
| Depois do 1.0.0, quebra de compatibilidade de API ou de `.env` | `release:major` |

## 5. Outros workflows

Previstos, ainda não escritos:

| Workflow | Gatilho | Faz |
|---|---|---|
| `ci.yml` | push em `dev`, PR para `main` | lint `ruff`, `mypy`, `pytest` no backend; `eslint`, `tsc`, `vitest` no frontend; build das imagens sem publicar |
| `docs.yml` | push que toque `.documentation/` | valida links internos entre os markdowns |
| `images.yml` | tag `v*` | **roadmap**: publica imagens em registro público |

## 6. Proteções em `main`

- Exigir pull request. Bloquear push direto.
- Exigir `ci.yml` verde.
- Exigir pelo menos a presença de uma label `release:*` antes do merge, via check simples, para que a
  falha do workflow de release seja exceção e não rotina.
