# ADR 015 — Pipeline de Release e Publicação

**Status:** Proposto · **Data:** 2026-11-26 · **Depende do** [ADR 013](ADR%20013%20Distribui%C3%A7%C3%A3o%20como%20Imagem%20Docker.md)

## Contexto

O fluxo atual corta uma tag quando um pull request com rótulo `release:patch|minor|major` é mesclado
em `main`. Funciona e tem uma propriedade que vale manter: **o tamanho do salto fica visível
enquanto a mudança ainda está em revisão**, e quem aprova vê qual versão vai sair.

Falta o resto. A tag não publica nada: não existe imagem, não existe release no GitHub, e quem quer
instalar continua clonando e construindo.

## Decisão

1. **Dois gatilhos, um caminho.** Continua o rótulo no pull request, e entra também
   `workflow_dispatch` com um parâmetro `release` de valores `patch`, `minor`, `major`. Os dois
   alimentam o mesmo cálculo de versão. O manual existe para republicar uma versão cuja publicação
   falhou depois da tag, e para cortar uma release que não vem de merge.

2. **A versão sai da última tag, não de arquivo.** `pyproject.toml` fica em `0.0.0` e a tag manda.
   Versão escrita em arquivo precisa de um commit para mudar, e esse commit precisa entrar antes da
   tag, o que cria uma janela em que os dois discordam.

3. **Ordem: calcular → taguear → construir → publicar imagem → criar a release.** A tag primeiro
   porque é ela que nomeia a imagem. Se a publicação falhar, a tag fica e o `workflow_dispatch`
   republica; o contrário — imagem publicada sem tag — deixaria um artefato que ninguém sabe de onde
   veio.

4. **A release do GitHub descreve o que mudou**, montada dos títulos dos commits desde a tag
   anterior, com o comando de instalação e o digest da imagem. Pré-1.0 é marcada como *pre-release*:
   `0.x` não promete compatibilidade, e o GitHub tem um campo para dizer isso.

5. **Falha com rótulo ausente, como hoje.** Merge sem rótulo não vira `patch` por omissão. Adivinhar
   `patch` publica uma quebra de compatibilidade como correção, e quem instalou seguindo a tag de
   minor recebe sem pedir.

6. **A imagem é construída uma vez, no release.** O CI de todo pull request continua fazendo lint,
   tipos e testes, e constrói a imagem **sem publicar**, só para provar que o Dockerfile está de pé.
   Descobrir que a imagem não constrói durante o release é descobrir tarde.

## Alternativas consideradas

- **Publicar imagem a cada push em `main`.** Dá `main` sempre instalável, mas transforma qualquer
  merge em entrega, e some a diferença entre "está no main" e "foi lançado".
- **Versão por convenção de commit (Conventional Commits).** Automático e sem rótulo, mas move a
  decisão para a mensagem de commit, que é escrita antes da revisão e quase nunca revisada. O
  rótulo é visível no pull request, que é onde se discute.
- **Só `workflow_dispatch`, sem rótulo.** Simples, mas transforma release em ato isolado, longe da
  mudança que a motivou.
- **Publicar a imagem e deixar a tag para depois.** Inverte a ordem e produz imagem órfã.

## Consequências

- O workflow precisa de `packages: write` além de `contents: write`.
- Build multi-arch com QEMU é lento. Cache por camada no registro reduz, e o custo cai no release,
  não em cada pull request.
- Quem instala passa a ter o que fixar: uma tag de imagem que corresponde a uma tag de código.
- O `docker-compose.yml` distribuído passa a apontar para a imagem publicada, e precisa de uma
  variável de versão para quem quiser fixar.
