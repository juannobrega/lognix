# Configuração

O Lognix se configura por três caminhos, e eles não competem: cada um serve a um momento
diferente. Quando o mesmo valor aparece em mais de um, **o de cima vence**.

| | Onde | Para quê |
|---|---|---|
| 1 | Variável de ambiente | o que o orquestrador injeta, e o que um operador muda às três da manhã sem editar arquivo |
| 2 | `config.yaml` | declarar a instalação inteira num arquivo que vai para o seu repositório |
| 3 | Interface | o dia a dia, por quem não quer editar YAML |

## Variáveis de ambiente

São o mínimo para o processo subir, antes de existir banco ou primeiro usuário.

| Variável | Padrão | O que é |
|---|---|---|
| `LOGNIX_SECRET_KEY` | — **obrigatória** | deriva a chave que criptografa credenciais. Perdê-la torna o que está guardado irrecuperável |
| `DATABASE_URL` | postgres local | o banco |
| `LOGNIX_PORT` | `8080` | porta publicada no host |
| `LOGNIX_PUBLIC_URL` | `http://localhost:8080` | como o Lognix é alcançado de fora |
| `LOGNIX_LOG_LEVEL` | `INFO` | |
| `LOKI_RETENTION_DAYS` | `15` | por quanto tempo as linhas de log ficam |
| `LOGNIX_CONFIG_FILE` | `/config/config.yaml` | onde procurar o arquivo abaixo |
| `LOGNIX_MCP_ALLOWED_HOSTS` | vazio | nomes aceitos no `Host` das chamadas [MCP](MCP.md), separados por vírgula. Vazio usa os de `LOGNIX_PUBLIC_URL`; `*` desliga a checagem |

## O arquivo `config.yaml`

Opcional. Sem ele, tudo se configura pela interface, como sempre. Com ele, a instalação sobe
pronta — útil para quem reinstala, para quem tem mais de um ambiente, e para quem quer a
configuração versionada junto do resto.

Copie `config/config.yaml.example` para `config/config.yaml` e suba.

```yaml
ai:
  enabled: true
  max_input_tokens: 12000

mcp:
  enabled: true

updates:
  check_enabled: true
  self_update_enabled: false

providers:
  - kind: openrouter
    name: OpenRouter
    default_model: anthropic/claude-sonnet-4.5
    credentials:
      api_key: ${OPENROUTER_API_KEY}
```

Três comportamentos que vale conhecer antes de usar:

**O que está no arquivo não se edita pela tela.** O campo aparece preenchido e desabilitado,
dizendo de onde veio. A alternativa — o arquivo semear o banco só na primeira subida — produz uma
instalação em que o arquivo diz uma coisa, a tela diz outra, e as duas parecem certas. Para voltar
a editar pela interface, tire a chave do arquivo.

**Segredo não se escreve ali.** Use `${VARIAVEL}`, resolvida do ambiente na subida. Variável
referenciada e não definida **impede a subida**, de propósito: um provedor que sobe com a chave
vazia só falha na primeira chamada, longe da causa.

**Arquivo inválido impede a subida**, dizendo o que está errado. Chave que o Lognix não conhece é
erro, não algo ignorado em silêncio — configuração ignorada é pior que ausente, porque quem
escreveu acredita que está valendo.

## O que roda dentro da imagem

A imagem do Lognix traz, além da API e da interface, o **Loki** e o **Alloy**. Os dois ficam lá
porque a configuração deles é do Lognix — a do Alloy é gerada pelo backend a cada mudança de
monitoramento — e uma combinação de versões que nunca foi testada não deveria ser possível de
montar por acidente. Os dois escutam só em `localhost` dentro do contêiner.

O **Postgres** fica de fora, porque é um banco: você pode já ter um, querer um gerenciado, ou
querer controlar backup e versão. É o único serviço que o `docker-compose.yml` sobe além do Lognix.

Se qualquer um dos três processos morrer, o contêiner inteiro cai e o Docker o reinicia. É
deliberado: um contêiner de pé com a API respondendo e o Loki morto parece saudável e parou de
coletar, que é o pior estado possível.
