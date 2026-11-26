# Lognix — Documentação

Duas áreas, com contratos diferentes. A distinção importa, porque elas envelhecem de formas
opostas.

| Pasta | O que é | Envelhece? |
|---|---|---|
| [Software/](Software/README.md) | Como o Lognix **funciona hoje**: instalar, operar, entender por dentro, contribuir. | Não pode. É atualizada junto com o código. |
| [Planning/](Planning/README.md) | **Por que** ele é assim: o que foi decidido, quando, com quais alternativas descartadas. | Pode, e tudo bem. Cada documento é datado e vale pelo que registrou. |

**Quando as duas discordam, a Software vence** para descrever comportamento, e a Planning continua
valendo para explicar a intenção. Um documento de planejamento que descreve uma tela que mudou não
está errado: está registrando como ela era quando aquela decisão foi tomada.

A exceção são os **ADRs**, em `Planning/02 Arquitetura/ADR/`. Esses são vivos: uma decisão que cai é
marcada como substituída ou ampliada por outro ADR, nunca apagada.

## Por onde começar

| Se você quer… | Vá para |
|---|---|
| rodar o Lognix | [Software/Instalação](Software/Instalação.md) |
| usar no dia a dia | [Software/Operação](Software/Operação.md) |
| entender como funciona por dentro | [Software/Arquitetura](Software/Arquitetura.md) |
| mexer no código | [Software/Desenvolvimento](Software/Desenvolvimento.md) |
| saber **por que** algo foi feito assim | [os ADRs](Planning/02%20Arquitetura/ADR/README.md) |
| saber o que vem depois | [Planning/08 Gestão/Roadmap](Planning/08%20Gestão/Roadmap.md) |

## Convenções

- Idioma: português. Identificadores de código, labels e chaves de config em inglês.
- Nomes de pastas e arquivos: **espaço como separador, iniciais maiúsculas**. Nunca hífen nem
  underscore no lugar de espaço.
- Toda pasta tem um `README.md` dizendo o que contém.
- Diagramas em Mermaid dentro do markdown.
- Nada de lista de endpoints escrita à mão: a referência da API é a OpenAPI que a própria
  instalação serve em `/api/docs`. Lista copiada para markdown é lista que envelhece calada.
