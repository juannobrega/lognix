# Lognix

Analisador de logs de containers Docker com IA, **sem instalar nada nos hosts monitorados**.

O Lognix se conecta por SSH às suas máquinas, lê os logs dos containers pela Docker API através de um
túnel, coleta tudo com **Grafana Alloy** para o **Loki**, e usa um modelo de linguagem para explicar o
que aconteceu, apontar a causa provável e, quando o projeto está ligado a um repositório GitHub,
indicar o trecho de código suspeito e abrir uma issue.

> **Estado:** em construção. Fase atual **0.1.0 Fundação**: instalação, login e usuários.
> O roadmap completo está em [.documentation/Planning](.documentation/Planning/README.md).

## Princípios

- **Nada no host.** O único requisito é SSH com acesso ao socket do Docker.
- **Somente leitura, garantido.** Um proxy dentro do Lognix só deixa passar requisições `GET` à Docker API. Nenhum comando de alteração chega ao host.
- **Logs primeiro, IA depois.** A interface de logs funciona com a IA desligada.
- **IA explicável e com custo visível.** Todo insight mostra as linhas que o embasaram e quanto custou.
- **Sem telemetria.** Nenhum dado sai do seu ambiente além do que você envia ao provider de IA e ao GitHub, e isso é avisado na interface.

## Instalação

Requisitos: Docker e Docker Compose em qualquer máquina.

```bash
git clone https://github.com/devjuannobrega/lognix.git
cd lognix
cp .env.example .env
# gere a chave e cole em LOGNIX_SECRET_KEY no .env
openssl rand -base64 48
docker compose up -d
```

Abra `http://localhost:8080`, crie o primeiro usuário e cadastre o primeiro host.

Guia completo em [.documentation/Software](.documentation/Software/README.md).

## Como funciona

```
Host monitorado                    Máquina do Lognix (docker compose)
/var/run/docker.sock ◄── SSH ──► backend ─► proxy somente leitura ─► Alloy ─► Loki
                                     │                                        ▲
                                     └── ciclo de análise ─► IA ─► insights ──┘
                                                 frontend React
```

## Desenvolvimento

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
# backend com hot reload em :8000, frontend: cd frontend && npm run dev
```

Testes: `cd backend && pytest` (precisa de um Postgres em `localhost:5432`, veja `tests/conftest.py`)
e `cd frontend && npm test`.

Trabalho acontece na branch `dev`. Pull requests para `main` levam uma label `release:patch`,
`release:minor` ou `release:major` e geram tag e release automaticamente.

## Licença

Ver [LICENSE](LICENSE).
