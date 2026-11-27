# ADR 020 — Alertas por E-mail via SMTP

**Status:** Aceito, construído na 1.6.0 · **Data:** 2026-11-27

## Contexto

O Lognix detecta um erro crítico às três da manhã, gera o insight, cita as linhas e calcula o
custo — e ninguém fica sabendo até alguém abrir a tela. Notificação existe, mas só dentro do
produto. Um analisador que acha o problema e não avisa entrega metade do que promete.

## Decisão

1. **SMTP, e não as APIs HTTP dos provedores.** SendGrid, Resend e Postmark têm API própria, e
   cada uma é uma integração com formato de credencial próprio. SMTP é um protocolo só que
   atende todos eles **e** o relay interno da empresa — que é o caso comum de quem instala
   software auto-hospedado e não quer que o alerta saia da rede.

2. **Presets dos provedores principais.** Host, porta e modo de segurança vêm preenchidos. Errar
   esses três é a causa número um de "não envia", e a mensagem de erro do SMTP é notoriamente
   ruim: `authentication failed` cobre desde senha errada até porta errada. Os campos continuam
   editáveis, porque Amazon SES muda de host por região e relay interno não tem preset.

3. **`smtplib` numa thread, sem dependência nova.** Enviar é raro — um alerta, um teste. Trazer
   `aiosmtplib` seria uma dependência para o que a biblioteca padrão faz, e `asyncio.to_thread`
   resolve o bloqueio.

4. **A regra fica na tela, não no código.** Severidade mínima, quais projetos, e se host caindo
   também avisa. O padrão é crítico e alto, todos os projetos, host caindo ligado — que é o que
   a maioria quer sem configurar nada.

5. **Só insight novo gera e-mail.** Recorrência atualiza a contagem do insight existente
   ([ADR 016](ADR%20016%20Deduplicação%20de%20Insights.md)) e **não** manda e-mail de novo. Sem
   isso, um erro persistente vira uma mensagem a cada ciclo, e o filtro do destinatário aprende
   a jogar o Lognix no lixo — que é o jeito mais eficiente de desligar o alerta sem querer.

6. **Falha ao enviar nunca derruba o ciclo de análise.** Ela vira registro no log e notificação
   na tela. O insight já existe e é o que importa; o e-mail é entrega, não produção.

7. **A senha é guardada criptografada**, como as credenciais dos provedores de IA, e nunca volta
   pela API — nem mascarada.

## Alternativas consideradas

- **Webhook genérico primeiro.** Mais simples de implementar e exige que a pessoa tenha para onde
  apontar. E-mail é o canal que todo mundo já tem. O webhook entra depois, pela mesma porta.
- **API de um provedor só, com SMTP depois.** Prende quem instala a uma empresa específica logo
  na primeira versão do recurso.
- **Fila de envio com repetição.** Entrega garantida pede estado persistente e repetição com
  recuo. Para alerta, chegar atrasado vale pouco: se falhou, o log e a tela contam.

## Consequências

- Nascem as configurações `smtp.*` e `alerts.*`, e uma área Integrações na interface — onde o
  GitHub App também vai morar quando chegar.
- A tela de teste manda um e-mail de verdade. É o único jeito honesto de dizer que funciona.
- O produto passa a ter um caminho de saída de dados a mais: o assunto e o corpo do alerta levam
  título, severidade e projeto. **Não levam linhas de log.** Quem quiser o conteúdo abre o
  Lognix, que é onde o acesso é controlado.
