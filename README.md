# Lognix

Analisador de logs de containers Docker com IA, **sem instalar nada nos hosts monitorados**.

O Lognix se conecta por SSH às suas máquinas, lê os logs dos containers pela Docker API através de um
túnel, coleta tudo com **Grafana Alloy** para o **Loki**, e usa um modelo de linguagem para explicar o
que aconteceu, apontar a causa provável e, quando o projeto está ligado a um repositório GitHub,
indicar o trecho de código suspeito e abrir uma issue.

> **Estado:** em construção, versão 0.9.0. Coleta, análise e IA funcionando; a integração com o
> GitHub é a próxima etapa. O roadmap está em [.documentation/Planning](.documentation/Planning/README.md).

## Princípios

- **Nada no host.** O único requisito é SSH com acesso ao socket do Docker.
- **Somente leitura, garantido.** Um proxy dentro do Lognix só deixa passar requisições `GET` à Docker API. Nenhum comando de alteração chega ao host.
- **Logs primeiro, IA depois.** A interface de logs funciona com a IA desligada.
- **IA explicável e com custo visível.** Todo insight mostra as linhas que o embasaram e quanto custou.
- **Sem telemetria.** Nenhum dado sai do seu ambiente além do que você envia ao provider de IA e ao GitHub, e isso é avisado na interface.

## Instalação

Requisitos: Docker e Docker Compose em qualquer máquina.

```bash
git clone https://github.com/juannobrega/lognix.git
cd lognix
cp .env.example .env
# gere a chave e cole em LOGNIX_SECRET_KEY no .env
openssl rand -base64 48
docker compose up -d
```

Abra `http://localhost:8080`, crie o primeiro usuário e cadastre o primeiro host.

Depois: crie o primeiro usuário e cadastre um host. O guia de
[Operação](.documentation/Software/Operação.md) mostra como preparar a máquina alvo, o que leva
dois comandos.

Guia completo em [.documentation/Software](.documentation/Software/README.md).

## O que ele faz hoje

- Cadastra hosts por SSH, com chave, chave com passphrase ou senha, e valida a conexão em seis
  etapas dizendo exatamente o que falta quando falha.
- Coleta os logs dos containers que você escolher, sem instalar nada no host.
- Mostra os logs ao vivo e em histórico, com filtro.
- Agrupa as linhas em padrões, classifica o nível e roda um ciclo de análise a cada 30 segundos.
- Detecta erros, eventos Docker críticos e anomalias estatísticas.
- Explica o que aconteceu com IA, citando as linhas que embasaram a conclusão, e registra o custo
  de cada chamada.
- Reconhece quando um container foi recriado por deploy e mantém o histórico do projeto.

## Como funciona

```
Host monitorado                    Máquina do Lognix (docker compose)
/var/run/docker.sock ◄── SSH ──► backend ─► proxy somente leitura ─► Alloy ─► Loki
                                     │                                        ▲
                                     └── ciclo de análise ─► IA ─► insights ──┘
                                                 frontend React
```

Detalhes em [.documentation/Software/Arquitetura.md](.documentation/Software/Arquitetura.md).

## Desenvolvimento

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
# backend com hot reload em :8000, frontend: cd frontend && npm run dev
```

Testes: `cd backend && pytest` (precisa de um Postgres em `localhost:5432`) e
`cd frontend && npm test`. Guia completo em
[Desenvolvimento](.documentation/Software/Desenvolvimento.md).

Trabalho acontece na branch `dev`. Pull requests para `main` levam uma label `release:patch`,
`release:minor` ou `release:major` e geram tag e release automaticamente.

## Licença

Ver [LICENSE](LICENSE).
