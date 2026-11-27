# Vínculo Container e Repositório

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21 · **Fase:** a seguir, 1 de 3

## 1. Regra

O usuário vincula cada projeto a um repositório **de código**, o codebase do sistema que roda no
container. O Lognix só ajuda a pré-preencher. Sem vínculo, o projeto é do tipo imagem e não recebe
diagnóstico de código nem issue.

## 2. Pré-preenchimento por labels OCI

| Label na imagem | Uso |
|---|---|
| `org.opencontainers.image.source` | URL do repositório. Se for `github.com/owner/repo`, sugere `owner` e `repo` |
| `org.opencontainers.image.revision` | commit. Vira `default_ref` sugerido |
| `org.opencontainers.image.version` | exibido, informativo |

A aba Repositório do projeto mostra o que foi lido e um botão "usar". O usuário pode alterar antes de
confirmar.

## 3. Validação do repositório

Ao confirmar, o backend verifica via GitHub App:

1. O App está instalado no repositório. Se não, mostra o link de instalação com o repositório pré-selecionado.
2. O repositório existe e é legível.
3. **É de código:** heurística obrigatória. Rejeita se a raiz contém só manifests, por exemplo
   predominância de `*.yaml` em `k8s/`, `manifests/`, `charts/`, `argocd/`, `flux/`, ou se há
   `kustomization.yaml` ou `Chart.yaml` na raiz sem código de aplicação. Aceita se há arquivos de
   linguagem de aplicação, `Dockerfile`, `pyproject.toml`, `package.json`, `go.mod`, `pom.xml`, etc.
   Em dúvida, aceita com aviso "este repositório parece de infraestrutura".
4. O `default_ref` existe. Se vier de revision OCI e não existir, cai para a branch padrão com aviso.

## 4. Qual commit usar no diagnóstico

Prioridade: `org.opencontainers.image.revision` da imagem **atualmente** rodando; depois
`RepositoryLink.default_ref`; depois branch padrão. O insight registra qual ref foi usada, para que o
usuário saiba se o código analisado é o que está rodando. Redeploy atualiza a revision automaticamente
quando a nova imagem a traz.

## 5. Redeploy e vínculo

O vínculo pertence ao `Container.id` do Lognix, que sobrevive ao redeploy por identidade de serviço.
Nada a refazer após deploy.
