# Guardrails

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Limites do que a IA pode fazer e o que o Lognix faz para conter erros dela.

## 1. Dados sensíveis saindo para o provider

Logs e código **saem** para o OpenRouter e, por ele, para o fabricante do modelo escolhido. Podem
conter senhas, tokens, e-mails, IPs, dados pessoais.

**Decisão de 2026-11-21: sem redação automática na v1.** A mitigação fica no roadmap. Em troca, a v1
é obrigada a ser **transparente**:

- Na tela de configuração de IA, aviso fixo: "Trechos de log e de código dos projetos monitorados são
  enviados ao OpenRouter e ao fabricante do modelo escolhido. Não ative em projetos cujos logs contenham
  dados que não podem sair do seu ambiente."
- O mesmo aviso no README do projeto e na documentação de instalação.
- O usuário consegue ver, em cada insight, exatamente o contexto que foi enviado. Nada é enviado sem
  ficar registrado.
- Variáveis de ambiente nunca são enviadas por valor. Monitoramento Docker seção 4.

Roadmap: redação automática de padrões óbvios, chaves de API, JWT, cartões, e-mails, sempre ligada,
e lista de regex extra configurável.

## 2. Alucinação

- Esquema fechado com `evidence_refs` obrigatório. Insight sem evidência não passa na validação.
- Evidências são resolvidas pelo backend a partir dos índices. Se a IA citar índice inexistente, a
  validação falha e vai para retry.
- `confidence` é exibido na interface. Abaixo de 0,4, o insight recebe selo "baixa confiança".
- O prompt instrui a dizer "causa não identificável nos dados" em vez de inventar.
- Diagnóstico de código só pode apontar arquivos que foram enviados. Área 09.

## 3. Ações

A IA nunca executa. Suas saídas só viram: insight gravado, e, na fase GitHub, issue aberta,
comentada ou reaberta. Nenhuma outra ação é derivada de saída de IA. Isso é testado: nenhum módulo
além do de issues consome `Insight` para produzir efeito externo.

## 4. Custo descontrolado

- Ciclo sequencial por container: no máximo uma chamada a cada 30 s mais a duração da chamada.
- **Sem deduplicação na v1.** Erro persistente gera insights repetidos e custo repetido. Aceito e
  documentado. Primeira melhoria do roadmap de IA.
- Concorrência limitada.
- Pausa automática em rate limit.
- Trigger manual tem limite de 1 por projeto por minuto.
- Tela de consumo sempre acessível.

## 5. Falhas

- Erro de rede, timeout ou esquema inválido após retry: `AICall.status = error` e notificação `ai_error`.
- IA desativada ou sem chave: a rotina roda tudo que é determinístico e **registra o evento** como
  `TriggerFired` sem insight. A interface lista esses eventos em "ocorrências sem análise". Confirmado
  em 2026-11-21.
- Nunca se cria insight vazio ou genérico para esconder uma falha.

## 6. Prompt injection via log

Logs são dados não confiáveis. Uma linha de log pode conter texto tentando instruir o modelo.
Mitigações na v1:

- Prompt de sistema declara que todo o conteúdo dos blocos é dado e nunca instrução.
- Blocos delimitados com marcadores claros e conteúdo escapado.
- Esquema fechado: mesmo que o modelo seja influenciado, só pode produzir campos do esquema, sem ação.
- Issue no GitHub é redigida pelo modelo, mas o backend monta a seção de evidências e o rodapé. Texto
  do modelo em issue é o único lugar onde conteúdo influenciado chegaria a terceiros. Aceito na v1,
  mitigado pelo tamanho máximo dos campos.
