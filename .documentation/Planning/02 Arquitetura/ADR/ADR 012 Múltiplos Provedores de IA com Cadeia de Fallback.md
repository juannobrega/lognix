# ADR 012 — Múltiplos Provedores de IA com Cadeia de Fallback

**Status:** Aceito · **Data:** 2026-11-25 · **Amplia o** [ADR 006](ADR%20006%20Provider%20de%20IA%20via%20OpenRouter%20e%20Contabilização%20de%20Custos.md)

## Contexto

O ADR 006 decidiu um provedor só, o OpenRouter, com a chave e o modelo guardados em duas linhas da
tabela `settings`. Isso levou o Lognix até a 0.9.0 e três limites apareceram na prática:

1. **Um provedor é um ponto único de falha.** Limite de uso estourado, chave revogada ou
   indisponibilidade do serviço deixam toda ocorrência sem análise, e o produto perde justamente a
   função que o define.
2. **Nem todo mundo pode usar OpenRouter.** Quem opera em AWS costuma precisar que a chamada ao
   modelo fique na própria conta, por contrato ou por não poder enviar dados a um intermediário. Quem
   já tem contrato com a OpenAI não quer uma camada a mais no caminho.
3. **Uma chave global não cabe em quem tem duas contas.** Projetos diferentes, orçamentos diferentes.

A abstração `AiProvider` prevista no ADR 006 estava no lugar, então a mudança é de modelo de dados e
de orquestração, não de integração.

## Decisão

1. **Provedor é entidade, não configuração.** A tabela `ai_providers` guarda tipo, nome, credenciais
   criptografadas, modelo padrão, estado do último teste e prioridade. `ai_models` guarda os modelos
   cadastrados em cada provedor, com preço por milhão de tokens. Dá para ter dois provedores do mesmo
   tipo, com contas diferentes, cada um com o próprio nome.
2. **Três tipos na 1.0.0: OpenRouter, OpenAI e Amazon Bedrock.** OpenRouter e OpenAI falam o mesmo
   formato de requisição e compartilham implementação. Bedrock não: usa a Converse API, assinatura
   SigV4 e identificadores de modelo próprios, e por isso é uma implementação separada.
3. **Credenciais declaradas pelo tipo, formulário montado pela interface.** Cada tipo publica os
   campos que pede (`CREDENTIAL_FIELDS`) com rótulo, obrigatoriedade e se é segredo. A interface se
   monta a partir de `GET /settings/ai/providers/kinds`. Acrescentar um tipo não exige mexer no
   frontend.
4. **Credencial é um bloco JSON criptografado, com o id do provedor no AAD.** Um bloco por provedor,
   em vez de uma linha por campo: Bedrock pede quatro campos e a chave de API da OpenAI pode vir
   acompanhada de organização e de URL base. O AAD amarra o texto cifrado àquele provedor, então um
   bloco copiado para outra linha não decifra.
5. **A ordem dos provedores é a cadeia de fallback.** A chamada vai ao primeiro provedor pronto —
   habilitado, com credencial e com modelo padrão. Erro de credencial, modelo inexistente, limite de
   uso ou indisponibilidade passam a vez ao seguinte. Quem estourou limite fica pausado alguns
   minutos, por provedor, e não trava a cadeia.
6. **Resposta fora do formato esperado não desce a cadeia.** Ela é retentada uma vez no mesmo
   provedor. Trocar de provedor não corrige formato: o problema é o modelo, não a credencial, e
   descer a cadeia só gastaria dinheiro duas vezes.
7. **Notificação uma vez por ocorrência, não por tentativa.** Uma cadeia de três provedores que falha
   inteira gera uma notificação, não três. O que a notificação diz é que a ocorrência ficou sem
   análise; o detalhe de cada tentativa fica no registro de chamadas.
8. **Toda tentativa é uma linha em `ai_calls`,** com provedor, número da tentativa e se foi fallback.
   É o que permite responder "qual provedor está falhando" em vez de só "a IA falhou".
9. **Preço por modelo, com origem registrada.** Quando o provedor informa o custo na resposta, é esse
   que vale. Quando não informa — o caso do Bedrock —, o custo é estimado pelo preço cadastrado no
   modelo, e a chamada fica marcada como estimativa. Modelo sem preço cadastrado soma zero, e a tela
   de consumo diz isso em palavras, porque consumo zero aparentando ser de graça é pior que um erro.
10. **A chave única da 0.9.0 migra sozinha.** Na primeira subida, se existir chave antiga em
    `settings` e nenhum provedor cadastrado, ela vira um provedor OpenRouter habilitado com o modelo
    que estava configurado, e as linhas antigas são apagadas. Ninguém reconfigura nada para subir de
    versão.

## Alternativas consideradas

- **Manter um provedor e documentar o risco.** Era o mais barato. Mas o produto existe para explicar
  o que aconteceu num container; ficar sem análise porque um serviço de terceiro recusou uma chamada
  é a falha mais cara que o Lognix pode ter.
- **Fallback automático por modelo, dentro do mesmo provedor.** Resolve o caso de um modelo
  sobrecarregado, não o de credencial revogada nem o de serviço fora. E o OpenRouter já faz isso
  internamente.
- **Usar o `boto3` para o Bedrock.** Traria o cliente síncrono inteiro da AWS para dentro de um
  backend `async`. Em vez disso, assinamos a requisição com `botocore.auth.SigV4Auth` e enviamos pelo
  `httpx` que já está no projeto: uma dependência de assinatura, não um SDK.
- **Cadeia implícita, derivada do último teste bem-sucedido.** Ordem automática é ordem que o usuário
  não controla. Se alguém quer que o provedor caro seja o segundo, isso é decisão de quem paga.
- **Uma linha de `settings` por campo de credencial.** Multiplicaria as chaves por provedor e tornaria
  o AAD por chave inútil, já que o vínculo que interessa é com o provedor.

## Consequências

- O modelo de dados cresce em duas tabelas e `ai_calls` ganha quatro colunas. Migração `0008`.
- `ai_has_credentials` deixa de olhar `settings` e passa a perguntar à cadeia. O interruptor geral da
  IA continua existindo e continua sendo o que decide se ela roda.
- A tela de configuração deixa de ter um campo de chave e passa a ter uma lista ordenável de
  provedores, cada um com credenciais, modelos e teste próprios.
- Observabilidade por provedor: chamadas, taxa de sucesso, fallbacks, latência média e p95, custo. É
  o que permite decidir qual provedor merece ser o principal.
- Acrescentar um quarto tipo passa a ser escrever uma classe e uma entrada em três dicionários.
  Ollama local, que o ADR 006 deixou no roadmap, cabe aqui sem decisão nova.
