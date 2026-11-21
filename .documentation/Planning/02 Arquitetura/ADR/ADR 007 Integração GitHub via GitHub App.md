# ADR 007 — Integração GitHub via GitHub App

**Status:** Aceito · **Data:** 2026-11-21

## Contexto

O Lognix precisa ler código de repositórios e abrir, comentar e reabrir issues. Há duas formas de
autenticar: token pessoal de um usuário ou um GitHub App instalado na conta ou organização.

## Decisão

**GitHub App.** O Lognix é registrado como App. O usuário instala o App nos repositórios que quer
vincular. O Lognix obtém tokens de instalação de curta duração com permissões mínimas: leitura de
conteúdo e escrita em issues. Nenhum token pessoal é armazenado.

A integração com GitHub **não entra na primeira fase de construção**. Ela chega na fase em que o
Lognix passa a detectar onde está o problema no código e abrir issues. Até lá, o produto funciona
sem GitHub: coleta, inventário, análise e insights baseados só em log.

## Alternativas consideradas

- **Token pessoal.** Mais rápido para começar, mas vinculado a uma pessoa, com permissões amplas e
  sem rotação. Inadequado para um produto que terceiros vão instalar.

## Consequências

- Quem instala o Lognix precisa registrar um GitHub App na própria conta e informar `App ID`, chave
  privada e `Installation ID` na interface. A documentação de instalação precisa guiar isso passo a passo.
- Issues aparecem como abertas pelo App, não por uma pessoa. Deixa claro que foi automático.
- A ordem das fases de construção precisa refletir que GitHub vem depois do núcleo.
