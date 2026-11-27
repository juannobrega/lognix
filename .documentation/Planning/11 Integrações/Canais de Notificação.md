# Canais de Notificação

**Status:** Construído na 1.6.0 · **Atualizado:** 2026-11-27

## Provedores com preset

Host, porta e segurança vêm preenchidos; todos os campos continuam editáveis.

| Provedor | Host | Porta | Segurança | Observação |
|---|---|---|---|---|
| Gmail / Google Workspace | `smtp.gmail.com` | 587 | STARTTLS | exige senha de app, não a senha da conta |
| Microsoft 365 / Outlook | `smtp.office365.com` | 587 | STARTTLS | |
| Amazon SES | `email-smtp.us-east-1.amazonaws.com` | 587 | STARTTLS | troque a região no host; a credencial SMTP não é a chave da AWS |
| SendGrid | `smtp.sendgrid.net` | 587 | STARTTLS | usuário é literalmente `apikey` |
| Mailgun | `smtp.mailgun.org` | 587 | STARTTLS | |
| Postmark | `smtp.postmarkapp.com` | 587 | STARTTLS | usuário e senha são o mesmo token |
| Resend | `smtp.resend.com` | 587 | STARTTLS | usuário é `resend` |
| Brevo | `smtp-relay.brevo.com` | 587 | STARTTLS | |
| Zoho | `smtp.zoho.com` | 587 | STARTTLS | |
| Servidor próprio | — | 25 | nenhuma | relay interno, o caso de quem não quer o alerta saindo da rede |

O preset preenche, não trava: Amazon SES muda de host por região, e relay interno não tem preset.

## A regra de disparo

| Configuração | Padrão | O que decide |
|---|---|---|
| `alerts.min_severity` | `high` | severidade mínima do insight que vira e-mail |
| `alerts.projects` | vazio | lista de projetos; vazio significa todos |
| `alerts.on_host_down` | ligado | host que cai também manda e-mail |

**Só insight novo dispara.** Recorrência atualiza a contagem do insight que já existe e não manda
nada: um erro persistente mandaria uma mensagem por ciclo, e o filtro de quem recebe aprenderia a
jogar o Lognix no lixo.

## O que vai na mensagem

Assunto com severidade, projeto e título. Corpo com host, projeto, severidade, causa provável,
ação sugerida, quantas ocorrências, e o link para o insight no Lognix.

**Não vai linha de log.** Caixa de e-mail é cópia que escapa do controle de acesso e fica para
sempre; quem quer a evidência abre o Lognix, onde se sabe quem entrou.

## Falhas

Enviar não é produzir: o insight já existe quando o e-mail é tentado. Falha de SMTP vira linha de
log e notificação na tela, nunca exceção que sobe para o ciclo de análise.

Sem repetição automática. Para alerta, chegar vinte minutos atrasado vale pouco — e uma fila com
recuo exigiria estado persistente para um ganho que o log já cobre.
