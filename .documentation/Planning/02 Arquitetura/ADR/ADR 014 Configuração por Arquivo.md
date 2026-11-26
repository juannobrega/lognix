# ADR 014 — Configuração por Arquivo

**Status:** Proposto · **Data:** 2026-11-26

## Contexto

Hoje a configuração do Lognix mora em dois lugares, por motivos diferentes e bons:

- **Ambiente** (`.env`), para o que precisa existir antes do primeiro login: `LOGNIX_SECRET_KEY`,
  `DATABASE_URL`, endereços do Loki e do Alloy. Sem isso o processo não sobe.
- **Banco** (tabela `settings` e `ai_providers`), para o que o usuário muda na interface:
  provedores de IA, limites de token, interruptor da IA. Segredos criptografados.

Falta um terceiro caso, que é o que motiva este ADR: **declarar a instalação inteira em um arquivo
versionável**. Quem sobe o Lognix por automação quer que SMTP, provedores de IA e banco venham
prontos, sem alguém clicar em cinco telas depois de cada `docker compose up`. E quer que esse
arquivo possa ir para um repositório.

## Decisão

1. **Um `config.yaml`, lido na subida**, em `/config/config.yaml` dentro do contêiner, com o caminho
   configurável por `LOGNIX_CONFIG_FILE`. Ausente, nada muda: tudo continua funcionando como hoje.

2. **Precedência, da maior para a menor: variável de ambiente → arquivo → banco → padrão.** O
   ambiente ganha do arquivo porque é o que o orquestrador injeta e o que um operador usa para
   corrigir uma instalação às três da manhã sem editar arquivo.

3. **O que o arquivo define, a interface mostra e não deixa editar.** Esta é a decisão que evita o
   pior modo de falha. A alternativa — o arquivo semear o banco só na primeira subida — produz uma
   instalação onde o arquivo diz uma coisa, a tela diz outra, e as duas estão "certas". Campo vindo
   do arquivo aparece preenchido, desabilitado e com a origem dita em palavras: *definido em
   config.yaml*. Quem quiser editar pela tela tira do arquivo.

4. **Segredo não se escreve no arquivo.** Todo valor aceita `${VAR}`, resolvido do ambiente na
   leitura. Variável faltando é **erro de subida**, não string vazia: um SMTP que sobe com senha
   em branco falha no primeiro e-mail, longe da causa.

   ```yaml
   smtp:
     host: smtp.exemplo.com
     port: 587
     username: lognix@exemplo.com
     password: ${SMTP_PASSWORD}
   ```

5. **Arquivo inválido impede a subida, com a linha e o motivo.** Configuração silenciosamente
   ignorada é pior que configuração ausente, porque quem escreveu acredita que ela está valendo.

6. **O arquivo é um espelho do que já existe, não um esquema novo.** Cada chave corresponde a algo
   que a interface já configura. Nada pode ser configurável só pelo arquivo: isso criaria um
   recurso invisível para quem usa a tela.

## Alternativas consideradas

- **Só variável de ambiente.** Funciona para valor escalar; vira sopa de letras para lista, e a
  cadeia de provedores é uma lista ordenada com credenciais por item. `AI_PROVIDER_2_API_KEY` é uma
  estrutura de dados fingindo ser uma variável.
- **O arquivo semeia o banco na primeira subida e some.** Simples de implementar e confuso de
  operar: mudar o arquivo depois não faz nada, e descobrir isso leva um tempo que ninguém tem.
- **O arquivo como única fonte, sem configuração pela interface.** Coerente, e o que faz o Alloy.
  Mas o Lognix é usado por quem não quer editar YAML — foi por isso que a chave de IA nasceu na
  tela, no ADR 006.
- **TOML ou JSON.** JSON não aceita comentário, e configuração sem comentário é configuração que
  ninguém entende seis meses depois. TOML serve, mas YAML é o que a vizinhança (compose, Alloy,
  Kubernetes) já usa.

## Consequências

- Nasce um módulo de configuração em camadas, hoje inexistente: `config.py` só lê ambiente.
- A API passa a informar, por campo, de onde veio o valor, para a interface poder desabilitar e
  explicar.
- O `config.yaml` precisa de documentação de referência em `Software/`, com exemplo completo.
- Fica aberto: o que fazer quando o arquivo muda com o sistema no ar. A proposta é reler só na
  subida — recarga a quente é conveniência que pode esperar.
