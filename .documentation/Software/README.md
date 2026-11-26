# Lognix — Documentação do Software

Como o Lognix funciona **hoje**. Esta é a área que precisa acompanhar o código: mudou
comportamento, muda aqui no mesmo pull request.

O **porquê** de cada decisão, com as alternativas descartadas, vive em
[../Planning/](../Planning/README.md). Quando as duas discordam sobre comportamento, esta vence.

| Documento | Para quem | Conteúdo |
|---|---|---|
| [Instalação](Instalação.md) | quem vai rodar o Lognix | requisitos, primeiro uso, variáveis, atualização |
| [Configuração](Configuração.md) | quem instala e automatiza | variáveis, `config.yaml`, o que roda dentro da imagem |
| [Operação](Operação.md) | quem usa no dia a dia | preparar hosts, monitorar containers, ler logs, insights, IA, métricas, backup |
| [Arquitetura](Arquitetura.md) | quem quer entender por dentro | o que cada peça faz e como os dados andam |
| [Desenvolvimento](Desenvolvimento.md) | quem vai mexer no código | rodar local, testar, estrutura, convenções |
| Referência de API | integradores | gerada pela própria instalação em `/api/docs` |

**Versão documentada:** 1.0.0.

Na raiz do repositório há ainda [CONTRIBUTING.md](../../CONTRIBUTING.md), com as convenções de
código e o fluxo de pull request, e [SECURITY.md](../../SECURITY.md), com o que o Lognix promete,
o que não promete e como relatar uma vulnerabilidade.
