# Instalação

**Versão:** 0.9.0

## Requisitos

- Docker 24 ou mais novo e Docker Compose v2, em qualquer máquina Linux ou macOS.
- Acesso de saída à internet para baixar as imagens.
- Para monitorar hosts: acesso SSH da máquina do Lognix até cada host.
- Para a análise por IA: uma chave do OpenRouter. Opcional; o resto funciona sem.

Porte medido: 10 hosts e 100 containers monitorados cabem em 2 vCPU e 4 GB. O backend usa cerca de
200 MB de memória. O disco é dominado pela retenção de logs no Loki, que depende do volume dos
containers e não do número deles.

## Primeiro uso

```bash
git clone https://github.com/juannobrega/lognix.git
cd lognix
cp .env.example .env
openssl rand -base64 48      # cole o resultado em LOGNIX_SECRET_KEY no .env
docker compose up -d
```

Abra `http://localhost:8080`. Como o sistema está vazio, a tela de criação do primeiro usuário
aparece. Esse usuário pode cadastrar os demais em Configurações › Usuários.

Em seguida, cadastre o primeiro host. O guia de [Operação](Operação.md) mostra como preparar a
máquina alvo, o que leva dois comandos.

## O que sobe

| Container | Função | Porta exposta |
|---|---|---|
| frontend | interface e proxy para a API | `LOGNIX_PORT`, padrão 8080 |
| backend | API, túneis, ciclos, IA; migrações rodam no início | nenhuma |
| postgres | metadados, insights, custos | nenhuma |
| loki | armazenamento dos logs | nenhuma |
| alloy | coleta, com config gerada pelo backend | nenhuma |

Só a porta do frontend fica acessível de fora.

## Variáveis do `.env`

| Variável | Obrigatória | Padrão | Uso |
|---|---|---|---|
| `LOGNIX_SECRET_KEY` | **sim** | — | criptografa credenciais e assina sessões. **Faça backup.** Sem ela, credenciais guardadas são irrecuperáveis |
| `LOGNIX_PORT` | não | 8080 | porta da interface |
| `LOGNIX_PUBLIC_URL` | não | http://localhost:8080 | URL pública, usada em links. Com `https://` os cookies passam a ser `Secure` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | não | lognix | credenciais do banco interno |
| `LOKI_RETENTION_DAYS` | não | 15 | retenção de logs e eventos |
| `LOGNIX_LOG_LEVEL` | não | INFO | nível de log do backend |
| `LOGNIX_ANALYSIS_CONCURRENCY` | não | 8 | ciclos de análise simultâneos |
| `LOGNIX_DB_POOL_SIZE` | não | 20 | conexões no pool do banco |
| `LOGNIX_DB_MAX_OVERFLOW` | não | 10 | conexões extras sob pico |

A chave do provider de IA **não** fica aqui: é cadastrada na interface e guardada criptografada no
banco, para poder ser trocada sem reiniciar.

## Atualização

```bash
git pull
docker compose up -d --build
```

As migrações rodam quando o backend inicia. Se o build for interrompido no meio, pode sobrar um
container com o nome tomado; nesse caso `docker rm -f lognix-backend-1` e suba de novo.

## Backup

Salve o banco, o volume do Loki e o `.env`. O procedimento completo, com restauração testada, está
em [Operação](Operação.md).

## Verificação

```bash
curl http://localhost:8080/api/v1/health
```

Devolve a versão e o estado de Postgres, Loki e Alloy. A tela Configurações › Sistema mostra o
mesmo com mais detalhe, incluindo os processos em execução por host.
