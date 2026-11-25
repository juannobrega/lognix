# Política de segurança

O Lognix guarda credenciais SSH de máquinas de produção e chaves de API. Levamos relatos de
segurança a sério.

## Como reportar

**Não abra uma issue pública para uma vulnerabilidade.** Use um destes caminhos:

- [Security advisory privado no GitHub](https://github.com/juannobrega/lognix/security/advisories/new),
  o caminho preferido.
- E-mail para o mantenedor, no endereço do perfil do GitHub.

Inclua, se puder: o que a falha permite fazer, como reproduzir, a versão afetada e o impacto que
você enxerga. Um relato com passos de reprodução vale muito mais que um aviso genérico.

Respondo em até 72 horas confirmando o recebimento. Se a falha procede, combinamos uma data de
divulgação, e seu nome entra no crédito da correção se você quiser.

## Versões suportadas

O projeto está em desenvolvimento ativo. Correções de segurança vão para a versão mais recente.
Não há suporte retroativo a versões anteriores.

## O que o Lognix promete

Estas são garantias de desenho, e quebrar qualquer uma delas é uma vulnerabilidade:

| Promessa | Como é garantida |
|---|---|
| Nenhum comando de alteração chega a um host monitorado | Proxy somente leitura com lista fechada de caminhos `GET`, verificado por teste automatizado no CI |
| Nada é instalado no host monitorado | O Alloy roda ao lado do Lognix; o host só precisa de SSH e acesso ao socket do Docker |
| Credenciais ficam criptografadas em repouso | AES-GCM com chave derivada de `LOGNIX_SECRET_KEY` por HKDF, com contextos separados |
| Segredos não voltam pela API | O `GET` informa apenas se existe uma credencial salva, nunca o valor |
| Nenhum dado sai do ambiente sem aviso | Só o provider de IA e, na fase do GitHub, o GitHub. Sem telemetria, sem verificação de atualização |

## O que o Lognix não promete

Ser honesto sobre os limites é parte da segurança:

- **Logs enviados à IA saem do seu ambiente.** Trechos de log vão para o provider configurado e,
  por ele, para o fabricante do modelo. Não há redação automática de dados sensíveis nesta versão.
  O aviso é fixo na tela de configuração.
- **Não há permissionamento.** Todo usuário autenticado acessa tudo, inclusive as credenciais
  mascaradas e os logs de todos os hosts. Papéis estão no roadmap.
- **Quem tem acesso ao socket do Docker controla o Docker.** O proxy impede o Lognix de alterar
  qualquer coisa, mas quem opera o host deve usar um usuário SSH dedicado.
- **Perder `LOGNIX_SECRET_KEY` é perder as credenciais.** Não há recuperação, por desenho.

## Endurecimento recomendado

Para quem opera o Lognix em ambiente sensível:

1. Usuário SSH dedicado em cada host, no grupo `docker` e em mais nada, sem shell
   (`usermod -s /usr/sbin/nologin`).
2. Chave em vez de senha, e chave só para esse uso.
3. A porta do Lognix atrás de um proxy reverso com TLS, com `LOGNIX_PUBLIC_URL` em `https://`
   para que os cookies de sessão virem `Secure`.
4. Backup do `.env` separado do backup do banco. Juntos, eles são a credencial completa.
5. Se os logs de um projeto contêm dados que não podem sair do ambiente, não ative a IA para ele.
