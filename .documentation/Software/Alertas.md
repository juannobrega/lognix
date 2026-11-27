# Avisar por e-mail

O Lognix detecta um erro crítico às três da manhã, gera o insight, cita as linhas e calcula o
custo — e ninguém fica sabendo até alguém abrir a tela. O canal de e-mail resolve isso.

Fica em **Integrações › E-mail**.

## 1. Escolha o provedor

A lista traz os principais já configurados — servidor, porta e modo de segurança preenchidos.
Errar esses três é a causa número um de "não envia", e a mensagem de erro do SMTP não ajuda:
`authentication failed` cobre desde senha errada até porta errada.

| Provedor | O que o site dele não deixa óbvio |
|---|---|
| **Gmail / Google Workspace** | exige **senha de app**, não a senha da conta, e a conta precisa de 2FA |
| **Microsoft 365 / Outlook** | |
| **Amazon SES** | troque a região no host; a credencial SMTP **não** é a sua chave da AWS |
| **SendGrid** | o usuário é literalmente `apikey`; a senha é a chave |
| **Mailgun** | |
| **Postmark** | usuário e senha são o **mesmo** token do servidor |
| **Resend** | o usuário é `resend` |
| **Brevo**, **Zoho** | |
| **Servidor próprio** | relay interno, para quem não quer o alerta saindo da rede |

O preset preenche, não trava: todos os campos continuam editáveis.

## 2. Prove que funciona

O botão **Enviar e-mail de teste** manda uma mensagem de verdade. É o único jeito honesto de
dizer que está configurado — e o erro, quando há, volta com o texto do servidor.

## 3. Escolha quando avisar

| | Padrão | |
|---|---|---|
| **Severidade mínima** | crítico e alto | o que é mais grave que isso também passa |
| **Projetos** | todos | em branco vale para qualquer um; com lista, só os listados |
| **Host desconectado** | ligado | enquanto um host está fora, os containers dele não são coletados nem analisados |

!!! info "Só insight novo vira e-mail"

    Recorrência atualiza a contagem do insight que já existe e **não** manda nada. Um erro
    persistente mandaria uma mensagem por ciclo de análise, e o filtro de quem recebe aprenderia
    a jogar o Lognix no lixo — que é o jeito mais eficiente de desligar o alerta sem querer.

## O que vai na mensagem

Assunto com severidade, projeto e título. Corpo com host, projeto, severidade, confiança, causa
provável, ação sugerida e o link para o insight.

!!! warning "Não vai linha de log"

    De propósito. Caixa de e-mail é cópia que escapa do controle de acesso e fica para sempre.
    Quem quer a evidência abre o Lognix, onde se sabe quem entrou.

## Quando o envio falha

Vira linha no log e notificação na tela — nunca derruba a análise. O insight já existe quando o
e-mail é tentado; entrega não pode atrapalhar produção.

Não há repetição automática. Para alerta, chegar vinte minutos atrasado vale pouco.

## Pelo arquivo

Para quem declara a instalação em [arquivo](Configuração.md), as chaves `smtp.*` e `alerts.*`
aceitam a mesma configuração. A senha nunca se escreve ali: use `${SMTP_PASSWORD}`, resolvida do
ambiente na subida.
