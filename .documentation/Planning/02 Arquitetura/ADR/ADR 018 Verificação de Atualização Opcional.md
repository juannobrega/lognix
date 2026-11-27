# ADR 018 — Verificação de Atualização Opcional

**Status:** Aceito, construído na 1.4.0 · **Data:** 2026-11-27

## Contexto

Quem instala o Lognix por `docker compose` não tem como saber que saiu versão nova. Descobre
quando lembra de olhar o GitHub, o que na prática é nunca: a instalação fica parada numa versão
por meses sem ninguém decidir isso.

O pedido original era mais ambicioso — um botão que atualiza o Lognix de dentro dele mesmo. Esse
pedido tem uma pedra que a descoberta não tem, e os dois não precisam andar juntos.

## A pedra do botão

**Um contêiner não troca a própria imagem.** O processo de dentro não consegue se substituir: quem
recria o contêiner é o Docker do host onde o Lognix roda. Para o botão existir, o contêiner do
Lognix precisaria do **socket do Docker do próprio host, com escrita** — acesso equivalente a root
naquela máquina, porque quem controla o socket cria qualquer contêiner que quiser. E mesmo com o
socket, um `compose up -d` disparado de dentro mata o processo que o chamou no meio da operação; o
jeito que funciona é um contêiner auxiliar efêmero que faz a troca e morre.

Nada disso fere a garantia de somente-leitura, que é sobre os **hosts monitorados**. Mas é um salto
de privilégio na máquina do Lognix, num produto cujo argumento é não pedir privilégio.

## Decisão

1. **Esta fase entrega só a descoberta.** Faixa dizendo que existe versão nova, com o link do
   changelog e o comando exato para copiar. O botão que atualiza fica para depois, e só com
   opt-in explícito de quem montar o socket. Ver [Roadmap](../../08%20Gestão/Roadmap.md).

2. **Desligada por padrão, e ligável na tela.** A documentação do produto promete, com estas
   palavras, "sem telemetria, sem verificação de atualização, sem chamadas a serviços do autor".
   Verificar atualização é uma chamada para fora, e ninguém deveria ganhar isso por atualizar de
   versão. Quem liga escolheu — como no MCP e na IA. A promessa muda de "não faz" para "não faz,
   a menos que você peça", que é uma frase que continua verdadeira.

3. **A fonte é a lista de tags do GHCR, não a API de releases do GitHub.** O que interessa ao
   usuário é a versão que ele **consegue baixar**, e as duas coisas já divergiram neste projeto:
   a v1.1.0 teve tag no git e release no GitHub sem imagem publicada por horas, porque o build
   foi cancelado. Anunciar uma versão cujo `docker pull` falha é pior que não anunciar nada.
   A consulta é anônima: `ghcr.io/token` com escopo de pull, e depois `/v2/<repo>/tags/list`.

4. **Só tags `X.Y.Z` entram na comparação.** A lista do registro traz também `latest`, `1`, `1.3`
   e `buildcache`. Comparar com qualquer uma delas daria resultado errado ou ruído.

5. **A comparação é numérica, por tupla.** `1.10.0` é maior que `1.9.0`, o que a comparação de
   texto erra — e já errou neste projeto, no passo de tags do release.

6. **Falha de rede não aparece como erro.** Registro fora do ar, DNS bloqueado ou instalação sem
   internet são o caso normal de quem roda isso numa rede fechada. A verificação devolve "não
   sei" e a tela não mostra nada; o log do backend guarda o motivo.

7. **O resultado é cacheado por 6 horas** e a consulta nunca acontece no caminho de uma
   requisição de página. Checar a cada abertura de tela transformaria navegação em tráfego
   externo, e o registro tem limite de requisição.

## Alternativas consideradas

- **Ligada por padrão.** É o que a maioria dos produtos faz, e é o que a nossa própria
  documentação promete não fazer. Promessa vale mais que conveniência.
- **Variável de ambiente em vez de configuração na tela.** Exigiria editar arquivo e reiniciar
  para algo que é decisão de quem usa, não de quem opera. Fica como configuração, com `config.yaml`
  aceitando a chave para quem declara a instalação inteira em arquivo.
- **API de releases do GitHub.** Mais simples, e mente quando o release existe e a imagem não.
- **Botão de atualizar agora.** Ver "A pedra do botão". Entra como fase própria, com opt-in.

## Consequências

- Nasce a configuração `updates.check_enabled`, desligada, e uma rota que a tela consulta.
- O parágrafo de privacidade do README e da documentação muda: "sem verificação de atualização"
  passa a "sem verificação de atualização, a menos que você ligue".
- Quando o botão de atualizar entrar, ele herda esta verificação como gatilho — e precisa mandar
  quem clica para o backup antes de confirmar, porque subir versão roda migração de banco.
