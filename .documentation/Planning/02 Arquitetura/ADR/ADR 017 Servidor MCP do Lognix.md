# ADR 017 — Servidor MCP do Lognix

**Status:** Aceito, construído na 1.2.0 · **Data:** 2026-11-27

## Contexto

O Lognix sabe coisas que um assistente de IA não tem como saber: quais containers existem, o que
quebrou nas últimas horas, qual padrão de erro é novo, quanto custou cada análise. Hoje esse
conhecimento só sai pela interface ou pela API REST, que exige alguém escrever o cliente.

O Model Context Protocol existe exatamente para esse caso: expor ferramentas que um assistente
chama sozinho durante uma conversa. "Por que o checkout caiu ontem à noite?" deveria ser
respondível sem ninguém abrir o navegador.

## Decisão

1. **Transporte HTTP, montado na própria aplicação**, em `/mcp`. O Lognix roda como serviço num
   contêiner; stdio exigiria publicar um segundo executável e explicar como instalá-lo ao lado.
   Com HTTP, apontar um cliente para `https://seu-lognix/mcp` basta.

2. **Autenticação por chave de API, não OAuth.** O protocolo prevê OAuth, que é o certo para um
   serviço multi-inquilino na internet. O Lognix é instalado pelo próprio dono, para si: montar
   servidor de autorização, registro dinâmico de cliente e fluxo de consentimento seria
   infraestrutura para um problema que ninguém tem aqui. Chave no cabeçalho `Authorization`,
   criada na interface.

3. **A chave é guardada com hash, como senha.** O valor aparece **uma vez**, na criação. Uma
   chave que pode ser relida é uma chave que vaza pelo backup, pelo log de auditoria e pela tela
   de quem está compartilhando o monitor.

4. **Permissão por escopo, não por ferramenta.** Três escopos, e a diferença entre eles é o que
   acontece quando a chave vaza:

   | Escopo | Dá acesso a | Se vazar |
   |---|---|---|
   | `leitura` | hosts, projetos, logs, padrões, insights, ocorrências | expõe seus logs |
   | `analise` | disparar análise manual | além disso, **gasta seu dinheiro** com IA |
   | `admin` | consumo da IA e estado do sistema | expõe custos e topologia |

   Escopo por ferramenta daria controle mais fino e uma tela que ninguém configura direito. Três
   grupos cabem na cabeça, e a pergunta "o que essa chave pode fazer" tem resposta curta.

5. **Nenhuma ferramenta escreve no host monitorado.** A garantia de somente leitura do produto
   vale aqui inteira: o MCP não ganha caminho que a interface não tem. A única ferramenta que
   *faz* algo é disparar uma análise, que é uma ação do próprio Lognix sobre dados que ele já
   coletou.

6. **Nenhuma ferramenta devolve credencial.** Nem chave de provedor, nem senha de SSH, nem
   variável de ambiente de container. O que não sai pela API REST também não sai aqui.

7. **Interruptor geral, desligado por padrão.** Como o da IA. Duas razões distintas: quem
   atualiza de versão não deveria ganhar um endereço que serve log sem pedir; e quem suspeita de
   vazamento precisa cortar tudo num clique, sem caçar chave por chave. Desligado, `/mcp`
   responde **503** — e não 401, porque a diferença entre "desligado aqui" e "sua chave não
   serve" é o que decide se a pessoa vai procurar na tela ou na chave. As chaves continuam
   guardadas: desligar não é revogar.

8. **Toda chamada é registrada**, com chave, ferramenta e horário, e a chave guarda o último uso.
   Sem isso não há como responder "quem consultou esses logs" nem decidir qual chave revogar.

## Alternativas consideradas

- **OAuth, como o protocolo prevê.** Correto para serviço público. Para uma instalação de um dono
  só, é um servidor de autorização inteiro para evitar um cabeçalho.
- **Reaproveitar o JWT da interface.** O token de acesso dura quinze minutos e o de renovação vive
  num cookie: nada disso serve para um cliente que precisa de credencial estável e sem navegador.
- **Servidor MCP em processo separado, por stdio.** Comum, e funciona bem para ferramenta de linha
  de comando. Aqui significaria distribuir um segundo artefato, mantê-lo na mesma versão do
  servidor e fazê-lo alcançar o banco — três problemas que o HTTP não tem.
- **Expor a API REST e pedir que o assistente a use.** Já é possível e ninguém faz: sem descrição
  de ferramenta, o modelo não sabe que `GET /projects/{id}/logs` aceita LogQL nem o que fazer com
  a resposta. A descrição é metade do valor do MCP.
- **Escopo por ferramenta.** Mais fino, e uma tela com vinte caixas que acaba toda marcada.

## Consequências

- Nasce a tabela `mcp_keys` e uma aba de configuração para criar, listar e revogar chaves.
- A dependência `mcp` entra no backend. É o SDK oficial; implementar o protocolo à mão
  significaria perseguir a especificação a cada versão.
- Logs do seu ambiente passam a poder sair por um caminho novo — para o assistente que a pessoa
  conectar, e daí para o fabricante do modelo dela. O aviso que existe na tela de Provedores
  precisa existir aqui também, porque é a mesma exposição por outra porta.
- Qualquer ferramenta nova precisa declarar escopo. Sem isso, cai no mais restritivo.

## O que a construção obrigou a decidir

Três coisas só apareceram ao montar o servidor, e nenhuma era previsível na mesa:

- **`admin` não implica `leitura`.** A hierarquia parecia natural e está errada: uma chave de
  automação de custos não deveria poder ler log por tabela. Quem quer tudo marca tudo.

- **A lista de `Host` aceitos precisa ser derivada da instalação.** O SDK valida o cabeçalho
  `Host` contra uma lista como defesa contra DNS rebinding, e o padrão dele aceita só
  `127.0.0.1` — ou seja, toda instalação com domínio próprio responderia **421**. A lista vem de
  `LOGNIX_PUBLIC_URL`, com `LOGNIX_MCP_ALLOWED_HOSTS` para quem publica por mais de um nome atrás
  de proxy.

- **`/mcp` tem que atender sem barra final.** Montado em `/mcp`, o roteador do Starlette responde
  307 para `/mcp/`, e POST redirecionado é algo que boa parte dos clientes HTTP não repete — a
  sessão morreria no redirecionamento, no primeiro `initialize`. O endereço que a tela mostra é o
  que precisa funcionar, então `/mcp` ganha rota própria além da montagem.

E uma que a tela obrigou: o **limite da análise manual passou para um módulo compartilhado**.
Estava na rota; com dois caminhos até o mesmo ciclo, um cliente MCP teria uma cota extra só por
entrar por outra porta.
