# Ambientes

**Status:** Aprovado em 2026-11-21 · **Atualizado:** 2026-11-21

## 1. Ambientes

| Ambiente | Onde | Como sobe | Para quê |
|---|---|---|---|
| **Desenvolvimento** | máquina do dev | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` | hot reload de backend e frontend, portas expostas, Grafana opcional para inspecionar o Loki |
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

Referência para 10 hosts e 100 containers monitorados com volume moderado: 2 vCPU, 4 GB RAM, 20 GB
de disco para 15 dias de logs. Medido na fase 0.7.0 e ajustado.
