# Lognix

**Análise de logs de containers com IA, sem instalar nada nos seus servidores.**

O Lognix se conecta por SSH às suas máquinas, lê os logs dos containers pela Docker API, guarda
tudo no Loki e analisa janelas curtas em ciclo contínuo. Quando algo quebra, ele explica o que
aconteceu, cita as linhas que embasaram a conclusão e mostra quanto custou a análise.

```bash
curl -O https://raw.githubusercontent.com/juannobrega/lognix/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/juannobrega/lognix/main/.env.example
cp .env.example .env            # gere LOGNIX_SECRET_KEY
docker compose up -d
```

Abra `http://localhost:8080` e crie o primeiro usuário. O guia de
[Instalação](Instalação.md) tem o resto.

## Três decisões que definem o produto

!!! info "Nada é instalado no host monitorado"

    O Grafana Alloy roda ao lado do Lognix e enxerga o Docker remoto por um túnel SSH. A máquina
    monitorada não ganha agente, nem daemon, nem alteração de configuração. O único requisito é
    SSH com acesso ao socket do Docker.

!!! info "Somente leitura, garantido por código"

    Entre o túnel e quem consome existe um proxy que recusa qualquer requisição que não seja
    `GET` numa lista fechada de caminhos. Não é promessa: é teste automatizado no CI, e um
    contador de requisições bloqueadas visível na interface.

!!! info "A IA não escreve evidências"

    Ela cita índices do contexto, e o backend troca por linhas e eventos reais. Um índice
    inexistente é recusado na validação. Isso fecha a porta para o pior modo de falha de um
    produto assim, que seria citar um log inventado.

## Por onde começar

| Se você quer… | Vá para |
|---|---|
| rodar o Lognix | [Instalação](Instalação.md) |
| declarar a instalação num arquivo | [Configuração](Configuração.md) |
| usar no dia a dia | [Operação](Operação.md) |
| entender como funciona por dentro | [Arquitetura](Arquitetura.md) |
| mexer no código | [Desenvolvimento](Desenvolvimento.md) |
| saber o que mudou | [Mudanças](CHANGELOG.md) |

A referência da API é gerada pela própria instalação, em `/api/docs`.

## Sobre esta documentação

Ela descreve como o Lognix funciona **hoje**, e muda no mesmo pull request que muda o
comportamento. O **porquê** de cada decisão, com as alternativas descartadas, vive na área de
[planejamento](https://github.com/juannobrega/lognix/blob/main/.documentation/Planning/README.md)
do repositório — inclusive as decisões que se mostraram erradas depois. Quando as duas discordam
sobre comportamento, esta aqui vence.

No repositório há ainda
[CONTRIBUTING.md](https://github.com/juannobrega/lognix/blob/main/CONTRIBUTING.md), com as
convenções de código e o fluxo de pull request, e
[SECURITY.md](https://github.com/juannobrega/lognix/blob/main/SECURITY.md), com o que o Lognix
promete, o que não promete e como relatar uma vulnerabilidade.
