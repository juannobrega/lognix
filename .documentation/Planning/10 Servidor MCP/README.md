# 10 — Servidor MCP

Define como um cliente de IA — Claude Code, Claude Desktop ou qualquer outro compatível — consulta o
Lognix pelo **Model Context Protocol**, em vez de a pessoa abrir a interface e procurar.

A inversão é o ponto: nas fases anteriores a IA era chamada **pelo** Lognix, com contexto que o
Lognix escolhia. Aqui é a IA de quem quer que seja que pergunta, e o Lognix responde — com o
inventário, os logs, os padrões e os insights que já produziu.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| [Ferramentas](Ferramentas.md) | As dez ferramentas, o que cada uma devolve, o escopo que exige, e o que não existe de propósito | Construído na 1.2.0 |
| [Chaves e Permissões](Chaves%20e%20Permissões.md) | Formato da chave, hash, escopos, expiração, revogação, auditoria | Construído na 1.2.0 |

## Decisões já tomadas

- **Transporte HTTP, montado na própria aplicação.** Ver [ADR 017](../02%20Arquitetura/ADR/ADR%20017%20Servidor%20MCP%20do%20Lognix.md). Nada de processo separado, nada de stdio: o Lognix já é um servidor HTTP com autenticação, e o cliente pode estar em outra máquina.
- **Chave de API, não OAuth.** O Lognix é auto-hospedado por uma equipe pequena; montar um servidor de autorização para isso seria custo sem ganho. A chave vai no `Authorization: Bearer`.
- **A chave aparece uma vez.** O banco guarda só o hash Argon2 e um prefixo curto, que serve para identificar a linha na tela — não para reconstruir a chave.
- **Três escopos: leitura, análise, administração.** A divisão não é por área da tela, é pelo que acontece quando a chave vaza: ler logs, gastar dinheiro com o provedor de IA, ou expor custos e topologia.
- **`admin` não implica `leitura`.** Quem quer tudo marca tudo, e isso fica visível na tela. Escopo largo por herança é o jeito mais fácil de uma chave de automação virar acesso a todos os logs.
- **Nenhuma ferramenta escreve.** Nem no host monitorado — isso o proxy somente leitura já garantia — nem no próprio Lognix. O servidor MCP não cadastra host, não marca container, não apaga insight. Uma chave vazada lê; não altera.
- **Nenhuma ferramenta devolve credencial.** Chave de provedor, senha de SSH e segredo de container não entram em nenhuma resposta, nem na ferramenta de estado do sistema.
- **Toda chamada fica registrada,** com a chave que a fez, duração e erro. Sem esse registro não há como decidir qual chave revogar.

## O que o escopo deixa de fora, e por quê

- **Análise sem limite.** `lognix_analisar_agora` existe, mas presa ao mesmo limite da interface — uma por minuto por projeto. A análise é um ciclo com janela e custo, e expô-la sem limite a um modelo convida a laço de chamadas.
- **Prompts e resources do MCP.** Ferramentas resolvem o caso de uso real — perguntar sobre um serviço. Prompt e resource entram se aparecer demanda concreta.
- **OAuth com consentimento por usuário.** Faz sentido num Lognix multi-inquilino, que não existe.

## Privacidade

Criar uma chave MCP é uma decisão de privacidade, não só de integração: as linhas de log saem do
Lognix para o cliente de IA de quem tem a chave, e dali para o modelo que aquele cliente usa. A
mesma ressalva que vale para os provedores de IA configurados vale aqui, com uma diferença — o
destino agora é escolhido por quem detém a chave, não pela configuração do Lognix. É o que a tela
diz ao lado de cada escopo, e é por isso que a recomendação é uma chave por cliente, com o escopo
mínimo.
