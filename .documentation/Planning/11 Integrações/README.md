# 11 — Integrações

Onde o Lognix fala com o mundo fora dele. Na interface é uma seção só, **Integrações**, e cada
item é um canal com configuração própria.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| [Canais de Notificação](Canais%20de%20Notificação.md) | E-mail por SMTP: provedores, regra de disparo, conteúdo da mensagem | Construído na 1.6.0 |
| [GitHub](../09%20Integração%20GitHub/README.md) | App, vínculo com repositório, diagnóstico e issues | Planejado, três fases a seguir |

## Por que uma área própria

Integração é o que **sai** do Lognix, e sair tem regra diferente de tudo o mais: cada canal é um
destino novo para dados que até então ficavam aqui dentro. Juntar os dois numa seção faz a
pergunta "o que este Lognix manda para fora, e para onde" ter uma resposta num lugar só.

A seção também separa o que configura **comportamento do produto** — IA, análise, retenção — do
que configura **conversa com terceiros**. Antes da 1.6.0 as duas coisas estavam no mesmo balaio.

## Decisões já tomadas

- **E-mail antes do GitHub.** A tela de configuração do GitHub App sozinha não faz nada: o que usa
  aquelas credenciais são as três fases seguintes. O e-mail fecha, sozinho, o buraco de "detecta e
  ninguém fica sabendo".
- **SMTP, não API de provedor.** Ver [ADR 020](../02%20Arquitetura/ADR/ADR%20020%20Alertas%20por%20E-mail%20via%20SMTP.md).
- **O alerta não leva linha de log.** Leva título, severidade, projeto e host. Quem quer o
  conteúdo abre o Lognix, onde o acesso é controlado — caixa de e-mail é cópia que escapa do
  controle de acesso e fica para sempre.
