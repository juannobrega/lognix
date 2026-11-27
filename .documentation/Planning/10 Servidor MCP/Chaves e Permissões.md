# Chaves e Permissões do MCP

**Status:** Construído na 1.2.0 · **Atualizado:** 2026-11-27

## Formato

`lgxmcp_` seguido de 32 bytes aleatórios em base64 url-safe. O prefixo serve a duas coisas: deixa
óbvio o que é a string quando ela aparece num log ou num arquivo de configuração alheio, e permite
que varredores de segredo a reconheçam.

O banco guarda `prefix` — o prefixo mais seis caracteres — e `key_hash`, Argon2. Verificar uma chave
é estreitar por prefixo e decidir por hash: o prefixo torna a busca indexada, o hash é quem autentica.
Seis caracteres não reconstroem a chave e bastam para a pessoa reconhecer a linha na tela.

## Escopos

| Escopo | Libera | O que acontece se a chave vazar |
|---|---|---|
| `leitura` | Hosts, projetos, logs, padrões, insights, ocorrências | Quem tem a chave lê os logs dos seus projetos |
| `analise` | `lognix_analisar_agora` | Além de ler, gasta dinheiro com o provedor de IA configurado |
| `admin` | Consumo da IA e estado do sistema | Expõe custos e a topologia da instalação |

A divisão **não é por área da tela** — é por consequência de vazamento. Foi a única régua que
produziu três grupos em vez de dez.

- **`admin` não implica `leitura`.** Uma chave de automação de custos não deveria poder ler log por
  tabela. Quem quer tudo marca tudo, e isso fica visível na listagem.
- **O escopo é conferido por chamada, não por conexão.** A conexão MCP é longa e o escopo da chave
  pode mudar — ou a chave ser revogada — no meio dela.
- **A tela mostra o risco de cada escopo ao lado da caixa de seleção.** Quem escolhe permissão sem
  saber o que ela expõe marca tudo.

## Ciclo de vida

- **Criação:** nome obrigatório, ao menos um escopo, validade opcional (30, 90, 365 dias ou sem
  expiração). O nome existe para responder "qual delas eu revogo".
- **Exibição única.** A chave em claro aparece uma vez, na resposta da criação. Não há endpoint que
  a devolva depois, porque não há onde ela esteja.
- **Desativar e reativar** sem perder o histórico, para suspender um cliente sob suspeita.
- **Revogar** apaga a chave. O registro de chamadas continua: é o que diz o que aquela chave fez.
- **Expiração** é conferida na verificação, não por rotina de limpeza — chave vencida simplesmente
  deixa de autenticar no instante em que vence.

## Auditoria

Cada chamada grava ferramenta, chave, duração, sucesso e erro. O nome da chave é copiado para a
linha em vez de referenciado: revogar a chave não deve apagar o rastro do que ela fez.

A tela mostra as últimas chamadas e, por chave, o total e o último uso. "Nunca usada" é um estado
próprio na listagem: chave criada e nunca usada é candidata a revogação, não a investigação.

## Proteção de transporte

O SDK do MCP valida o cabeçalho `Host` contra uma lista, como defesa contra DNS rebinding. O padrão
dele aceita só `127.0.0.1`, o que responderia **421** em qualquer instalação com domínio próprio. O
Lognix deriva a lista de `LOGNIX_PUBLIC_URL` e aceita também as formas de localhost; quem publica o
Lognix por mais de um nome atrás de proxy usa `LOGNIX_MCP_ALLOWED_HOSTS`, com `*` desligando a
checagem.
