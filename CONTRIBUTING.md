# Contribuindo com o Lognix

Obrigado pelo interesse. Este guia é curto porque o projeto tem uma regra que explica quase tudo.

## A regra que governa o projeto

**Nada é construído antes de estar mapeado.** O planejamento inteiro vive em
[`.documentation/Planning`](.documentation/Planning/README.md): visão, arquitetura, decisões,
fases. Código novo que muda comportamento vem acompanhado da atualização do documento
correspondente, e decisão não óbvia vira um
[ADR](.documentation/Planning/02%20Arquitetura/ADR/README.md).

Isso não é burocracia. É o que permite voltar meses depois e entender por que algo é do jeito que
é, em vez de descobrir no `git blame`.

## Antes de abrir um pull request

1. **Abra uma issue primeiro** se a mudança é maior que uma correção pontual. Evita que você
   escreva código que colide com uma decisão já registrada.
2. **Leia o documento da área** que você vai mexer. Se a sua mudança contradiz o que está lá, a
   conversa é sobre mudar a decisão, não sobre contornar.
3. **Rode as verificações locais.** O guia está em
   [Desenvolvimento](.documentation/Software/Desenvolvimento.md).

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/mypy lognix && .venv/bin/pytest
cd frontend && npm run lint && npm run typecheck && npm test -- --run && npm run build
```

## Pull requests

- Saem de `dev` e voltam para `dev`. Só mantenedores fazem o merge de `dev` em `main`.
- Levam exatamente uma label de release: `release:major`, `release:minor`, `release:patch` ou
  `release:skip`. Sem label, o workflow falha de propósito.
- Descrevem **o que muda e por quê**. Diga o que você verificou e como.
- Testes acompanham comportamento novo. Para correção de bug, um teste que falha antes da correção
  vale mais que três depois.

## Convenções de código

As que importam, porque vieram de problemas reais:

- **Um módulo por sistema externo.** Só `docker/` fala com a Docker API, só `loki/` com o Loki,
  só `ai/` com o provider de IA.
- **Trabalho de CPU cede o event loop.** Laço longo precisa de `await asyncio.sleep(0)` de tempos
  em tempos, ou a API trava junto. Ver
  [ADR 010](.documentation/Planning/02%20Arquitetura/ADR/ADR%20010%20Desempenho%20do%20Ciclo%20de%20An%C3%A1lise.md).
- **Escrita no banco dentro de tarefa cancelável** usa `asyncio.shield`, e quem para a tarefa
  espera o trabalho blindado terminar. Sem isso sobram conexões com transação aberta.
- **Erros da API** sempre em `{"error": {"code", "message", "action"}}`. O `action` diz o que a
  pessoa deve fazer, e é obrigatório em erro de conexão.
- **Textos da interface e mensagens de erro em português.** Identificadores, labels e chaves de
  configuração em inglês.
- **Nenhum teste fala com serviço externo de verdade.** Há um falso para SSH, Docker, Loki, Alloy
  e o provider de IA, todos em `backend/tests/`.

## O que provavelmente não será aceito

- Mudança que quebre a garantia de somente leitura nos hosts monitorados.
- Telemetria, verificação automática de atualização, ou qualquer chamada a um serviço que o usuário
  não pediu.
- Dependência pesada para resolver um problema pequeno.
- Mudança de comportamento sem a atualização do documento correspondente.

## Reportando bugs

Abra uma issue com: o que você esperava, o que aconteceu, a versão (aparece em Configurações ›
Sistema) e, se der, o trecho do log do backend. Para vulnerabilidades, siga o
[SECURITY.md](SECURITY.md) e não abra issue pública.
