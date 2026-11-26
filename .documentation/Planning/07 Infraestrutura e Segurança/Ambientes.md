# Ambientes

**Status:** Aprovado em 2026-11-21 · **Atualizado:** 2026-11-21

## 1. Ambientes

| Ambiente | Onde | Como sobe | Para quê |
|---|---|---|---|
| **Desenvolvimento** | máquina do dev | `docker compose up -d` para a infra, backend e frontend fora do Docker | hot reload de verdade, com o venv e o Vite locais |
| **Instalação do usuário** | qualquer máquina com Docker | `docker compose up -d` | o produto. É o ambiente de "produção" de quem usa |
| **CI** | GitHub Actions | serviços Postgres e Loki efêmeros | testes |

Não há staging próprio: o projeto é de código aberto e instalado por terceiros. O "staging" é a
instalação do próprio autor rodando `dev` antes do merge.

## 2. `docker-compose.yml`, instalação padrão

```yaml
services:
  frontend:   # nginx: estáticos + proxy /api e /ws → backend
    ports: ["${LOGNIX_PORT:-8080}:80"]
  backend:    # FastAPI, LoopManager
    volumes: [tunnels:/tunnels, alloy-config:/alloy-config]
    depends_on: [postgres, loki]
  postgres:
    volumes: [postgres-data:/var/lib/postgresql/data]
  loki:
    volumes: [loki-data:/loki]
  alloy:
    volumes: [tunnels:/tunnels, alloy-config:/etc/alloy]
    depends_on: [loki]
volumes: { postgres-data, loki-data, tunnels, alloy-config }
```

Regras:

- **Só a porta do frontend é exposta.** Backend, Postgres, Loki e Alloy ficam na rede interna.
- Imagens construídas localmente no 1.0.0, `build:` no compose. Imagens publicadas no roadmap.
- O backend precisa do binário `ssh` na imagem se a decisão da fase 0.2.0 for subprocesso.
- Healthchecks em todos os serviços; backend espera Postgres e Loki prontos.
- `restart: unless-stopped`.
- **Config do Alloy fora de `/etc/alloy`.** A imagem oficial traz uma config padrão nesse caminho; um volume vazio montado ali herda esse arquivo e o Alloy passa a rodar a config da imagem em vez da nossa. Descoberto na 0.1.0. O volume fica em `/lognix/alloy`.


### Cache dos estáticos, e por que o nginx não pode responder tudo

O `index.html` tem nome fixo e conteúdo novo a cada deploy; os bundles têm hash no nome e conteúdo
que nunca muda. Então são duas políticas opostas: `no-cache` no primeiro, `immutable` por um ano nos
segundos.

O que amarra as duas é o `=404` em `/assets/`. O fallback de SPA (`try_files ... /index.html`)
responderia qualquer caminho desconhecido com o index e **status 200** — inclusive um bundle que
saiu no deploy anterior. Um browser com o index antigo em cache pediria o JS antigo, receberia HTML
com 200, o módulo não parsearia e a tela ficaria branca, sem erro de rede e sem log no servidor.
Falha cara de diagnosticar, e a correção é uma linha.

Cabeçalho de segurança no nginx se repete em cada `location` de propósito: um bloco que declara o
próprio `add_header` não herda os do pai. Tirar a repetição apaga os cabeçalhos naquele caminho sem
aviso nenhum.

Os dois `.dockerignore` existem pela mesma razão: o build roda dentro da imagem, então
`node_modules`, `dist` e `.venv` da máquina de quem builda não têm por que entrar no contexto — eram
330 MB enviados ao daemon a cada build, e um `node_modules` de macOS dentro de uma imagem Alpine é
um jeito silencioso de quebrar binário nativo.

## 3. `.env`

Arquivo `.env.example` versionado com todos os valores e comentários. Obrigatórios sem padrão:
`LOGNIX_SECRET_KEY`. Tudo o mais tem padrão funcional. Instrução de gerar a chave com um comando
no README.

## 4. Primeiro uso

1. `cp .env.example .env`, gerar `LOGNIX_SECRET_KEY`.
2. `docker compose up -d`.
3. Abrir `http://localhost:8080`, criar o primeiro usuário.
4. Cadastrar o primeiro host.

Meta: do clone ao primeiro log na tela em menos de 10 minutos, O1 da Visão.

## 5. Atualização

`git pull && docker compose up -d --build`. Migrações rodam no startup do backend. Nunca migração
destrutiva sem passo manual documentado.

## 6. Backup

O que precisa ser salvo: volume `postgres-data`, volume `loki-data`, e o `.env`, em especial
`LOGNIX_SECRET_KEY`. Sem a chave, o banco restaurado tem credenciais ilegíveis. Procedimento com
`pg_dump` e cópia do volume do Loki documentado em `Software/` na fase 0.7.0.

## 7. Requisitos de máquina

**Medido em 2026-11-24** com 10 hosts e 100 containers monitorados, 200 linhas por janela: backend
em 206 MB de memória, banco em 12 MB após 2000 ciclos, ciclo determinístico com p95 de
948 ms. Para esse porte, 2 vCPU e 4 GB bastam. O disco é dominado pela retenção de logs no
Loki, que depende do volume dos containers e não do número deles.
