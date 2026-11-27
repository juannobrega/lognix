<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="frontend/public/logo-on-dark.png">
  <img src="frontend/public/logo-on-light.png" alt="Lognix" width="420">
</picture>

**Análise de logs de containers com IA, sem instalar nada nos seus servidores.**

[![ci](https://github.com/juannobrega/lognix/actions/workflows/ci.yml/badge.svg)](https://github.com/juannobrega/lognix/actions/workflows/ci.yml)
[![licença Apache 2.0](https://img.shields.io/badge/licen%C3%A7a-Apache%202.0-blue)](LICENSE)
[![versão](https://img.shields.io/github/v/tag/juannobrega/lognix?label=vers%C3%A3o&sort=semver)](https://github.com/juannobrega/lognix/releases)

</div>

---

O Lognix se conecta por SSH às suas máquinas, lê os logs dos containers pela Docker API, guarda
tudo no Loki e analisa janelas curtas em ciclo contínuo. Quando algo quebra, ele explica o que
aconteceu, cita as linhas que embasaram a conclusão e mostra quanto custou a análise.

Nada é instalado no host monitorado. O único requisito é SSH com acesso ao socket do Docker.

## Por que existe

Ferramentas de observabilidade mostram os logs. Poucas os **explicam**. O custo de triagem de um
incidente é dominado por leitura humana de texto repetitivo, às três da manhã, numa janela de
terminal.

O Lognix tenta resolver a parte chata: agrupa as linhas em padrões, detecta o que fugiu do normal
e, quando acha que vale, pede a um modelo de linguagem para explicar em português o que está
acontecendo, apontando as evidências.

## Três decisões que definem o produto

**Nada no host.** O Grafana Alloy, que coleta os logs, roda ao lado do Lognix e enxerga o Docker
remoto através de um túnel SSH. A máquina monitorada não ganha agente, nem daemon, nem alteração
de configuração.

**Somente leitura, garantido por código.** Entre o túnel e quem consome existe um proxy que recusa
qualquer requisição que não seja `GET` numa lista fechada de caminhos. Não é promessa: é teste
automatizado no CI, e um contador de requisições bloqueadas visível na interface.

**A IA não escreve evidências.** Ela cita índices do contexto, e o backend troca por linhas e
eventos reais. Um índice inexistente é recusado pela validação. Isso fecha a porta para o pior modo
de falha de um produto assim, que seria citar um log inventado.

## Começando

Requisitos: Docker e Docker Compose em qualquer máquina. Dois arquivos, nenhum clone — a imagem
vem publicada.

```bash
curl -O https://raw.githubusercontent.com/juannobrega/lognix/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/juannobrega/lognix/main/.env.example
cp .env.example .env
openssl rand -base64 48      # cole em LOGNIX_SECRET_KEY no .env
docker compose up -d
```

Sobem dois contêineres: o Lognix e o Postgres. O **Loki** e o **Alloy** rodam dentro da imagem,
porque a configuração dos dois é gerada pelo próprio sistema — assim não existe combinação de
versões que nunca foi testada. Para fixar uma versão em vez de seguir a última, ponha
o número em `LOGNIX_VERSION` no `.env`.

Abra `http://localhost:8080`, crie o primeiro usuário e cadastre um host. Preparar a máquina alvo
leva dois comandos:

```bash
sudo useradd -m lognix && sudo usermod -aG docker lognix
ssh-copy-id -i ~/.ssh/sua-chave.pub lognix@HOST
```

O cadastro valida a conexão em seis etapas e, quando falha, diz exatamente o que falta.

## O que já funciona

- Hosts por SSH, com chave, chave com passphrase ou senha, e reconexão automática.
- Coleta dos containers que você escolher, a partir do momento da marcação.
- Logs ao vivo e em histórico, com filtro de texto, nível e período.
- Agrupamento em padrões, classificação de nível e um ciclo de análise a cada 30 segundos.
- Detecção de erros, eventos Docker críticos e anomalias estatísticas.
- Explicação por IA com evidências rastreáveis, custo por chamada e tela de consumo.
- Reconhecimento de redeploy: recriar um container não apaga o histórico do projeto.
- Métricas Prometheus e uma tela de Sistema que mostra o estado de cada processo.

**Em construção:** a integração com o GitHub, que vai ligar o erro ao trecho de código que o
causou e abrir a issue.

## Como funciona

```
Host monitorado                      Máquina do Lognix
┌──────────────────┐   SSH    ┌────────────────────────────────────────────┐
│ /var/run/        │◄────────►│ backend ──► proxy somente leitura          │
│   docker.sock    │  túnel   │    │              ▲                        │
│                  │          │    │           alloy ──► loki              │
│ containers…      │          │    │                      ▲                │
└──────────────────┘          │    └── ciclo de análise ───┘                │
                              │           │                                 │
                              │           └─► IA ─► insights ─► interface   │
                              └────────────────────────────────────────────┘
```

Detalhes em [Arquitetura](.documentation/Software/Arquitetura.md).

## Privacidade

Trechos de log saem do seu ambiente **apenas** para o provider de IA que você configurar, e isso
é avisado na tela. Não há redação automática de dados sensíveis nesta versão. Variáveis de
ambiente nunca são enviadas por valor, só por nome.

Fora isso, nada sai: sem telemetria, sem verificação de atualização, sem chamadas a serviços do
autor. A IA é opcional e o resto funciona com ela desligada.

## Documentação

**[juannobrega.github.io/lognix](https://juannobrega.github.io/lognix/)** — instalação,
configuração, operação e o histórico de mudanças.

## Stack

Python com FastAPI, PostgreSQL, Grafana Alloy e Loki no backend. React com Vite e TypeScript no
frontend, servido pela própria API. Imagem única publicada em `ghcr.io/juannobrega/lognix`, para
`linux/amd64` e `linux/arm64`, com proveniência e SBOM.

## Contribuindo

[CONTRIBUTING.md](CONTRIBUTING.md). Vulnerabilidades: [SECURITY.md](SECURITY.md), em privado.

## Licença

[Apache 2.0](LICENSE).
