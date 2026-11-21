# Instalação

**Versão:** 0.3.0

## Requisitos

- Docker 24+ e Docker Compose v2 em qualquer máquina Linux ou macOS.
- Acesso de saída à internet para baixar imagens.
- Para monitorar hosts (fase 0.2.0): acesso SSH do Lognix até cada host.

## Primeiro uso

```bash
git clone https://github.com/devjuannobrega/lognix.git
cd lognix
cp .env.example .env
openssl rand -base64 48      # cole o resultado em LOGNIX_SECRET_KEY no .env
docker compose up -d
```

Abra `http://localhost:8080`. Como o sistema está vazio, a tela de criação do primeiro usuário
aparece. Esse usuário pode cadastrar os demais em Configurações › Usuários.

## O que sobe

| Container | Função | Porta exposta |
|---|---|---|
| frontend | interface e proxy para a API | `LOGNIX_PORT`, padrão 8080 |
| backend | API, migrações automáticas no início | nenhuma |
| postgres | metadados | nenhuma |
| loki | armazenamento de logs | nenhuma |
| alloy | coleta de logs via túneis, config gerada pelo backend | nenhuma |

Só a porta do frontend fica acessível de fora.

## Variáveis do `.env`

| Variável | Obrigatória | Padrão | Uso |
|---|---|---|---|
| `LOGNIX_SECRET_KEY` | **sim** | — | criptografa credenciais e assina sessões. **Faça backup.** Perder a chave torna credenciais guardadas irrecuperáveis |
| `LOGNIX_PORT` | não | 8080 | porta da interface |
| `LOGNIX_PUBLIC_URL` | não | http://localhost:8080 | URL pública, usada em links. Com `https://` os cookies passam a ser `Secure` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | não | lognix | credenciais do banco interno |
| `LOKI_RETENTION_DAYS` | não | 15 | retenção de logs e eventos |
| `LOGNIX_LOG_LEVEL` | não | INFO | nível de log do backend |

## Atualização

```bash
git pull
docker compose up -d --build
```

As migrações de banco rodam automaticamente quando o backend inicia.

## Backup

Salve três coisas: o volume `postgres-data`, o volume `loki-data` e o arquivo `.env`.

```bash
docker compose exec postgres pg_dump -U lognix lognix > lognix-$(date +%F).sql
```

Restaurar o banco sem o mesmo `LOGNIX_SECRET_KEY` deixa as credenciais ilegíveis.

## Cadastrar o primeiro host

Veja [Operação](Operação.md) para preparar o host. Na interface: Hosts › Cadastrar host. A validação
mostra seis etapas e, em cada falha, o que fazer.

## Verificação

`curl http://localhost:8080/api/v1/health` devolve a versão e o estado de Postgres, Loki e Alloy.
Na 0.1.0, só o Postgres é obrigatório; Loki e Alloy aparecem como informativos.
