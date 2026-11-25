# ADR 011 — Identidade Visual do Lognix

**Status:** Aceito · **Data:** 2026-11-24

## Contexto

A interface construída até a 0.8.0 funcionava, mas parecia amadora. Dois problemas distintos
estavam misturados:

1. **Nenhuma identidade visual.** Cinzas neutros, azul padrão, sombras em cartões. Nada errado,
   nada que fosse do Lognix.
2. **Componentes caseiros onde não deviam ser.** `<select>` nativo, `window.confirm`, abas feitas
   com botões, nenhum diálogo, nenhum tooltip. São os componentes difíceis de acertar em
   acessibilidade, e os que mais denunciam amadorismo.

Uma primeira tentativa adotou a linguagem do Coolify tal como está documentada no `DESIGN.md`
dele: roxo `#6b16ed`, barra lateral `#120e1a`, aresta inferior de 2px nos botões, tile de
gradiente no item ativo. Funcionou visualmente e **foi rejeitada com razão**: aquilo é a
identidade de outro produto. Um projeto que vai ser publicado precisa parecer com ele mesmo.

## Decisão

**A identidade nasce da marca.** O símbolo do Lognix é um gradiente de azul elétrico para ciano
para violeta, sobre barras verticais de altura variável, que são um gráfico de sinal. A interface
deriva daí.

| | |
|---|---|
| Marca | `#2f6bff` azul elétrico → `#22d3ee` ciano → `#a855f7` violeta |
| Acento | `#2060e6` no claro, `#4d8bff` no escuro: o azul da marca calibrado para texto pequeno e foco |
| Superfícies escuras | canvas `#080b11`, painel `#0f141d`, barra lateral `#0b0f16`. **Puxam para o azul**, nunca cinza neutro |
| Tipografia | Geist Sans e Geist Mono, servidas pelo pacote porque a CSP bloqueia CDN |
| Densidade | 11px meta, 13px interface, 14px campos, 23px títulos; controles de 32px |

**Três assinaturas próprias**, que substituem as do Coolify:

1. **Barra de sinal.** O item ativo da navegação ganha uma barra vertical de 3px com o gradiente
   da marca, que cresce a partir do centro. É o motivo das barras do símbolo. O cartão de insight
   repete o gesto no hover. Onde o Coolify usa um tile preenchido, o Lognix usa uma barra.
2. **Botão com brilho interno.** O primário é o azul da marca com um realce de 1px no topo, como
   um painel iluminado por cima. Sem a aresta de profundidade de 2px: num painel de operação,
   botão que pula a cada hover cansa.
3. **Ponto com halo.** Estados usam um ponto de 7px com um halo de cor diluída ao redor, e o halo
   pulsa em estados de transição. Um painel de monitoramento mostra coisas que estão acontecendo
   agora; o ponto chapado não transmite isso.

Some-se o **fio de marca**: um gradiente de 2px no topo dos blocos que lideram a tela, e o
componente `SparkBars`, que desenha séries curtas com as barras da marca sem trazer uma biblioteca
de gráficos.

**Componentes: primitivas do Radix UI, estilo nosso em CSS Modules.** Radix dá comportamento e
acessibilidade dos componentes difíceis sem impor estética: diálogo com foco preso e `Esc`, select
navegável por teclado, tooltip, switch.

## O que veio do Coolify, e por quê não é cópia

Três ideias foram mantidas porque não são identidade, são boa prática de painel denso, e aparecem
em qualquer ferramenta séria do gênero:

- **Camadas em vez de caixas.** Profundidade por degraus de superfície e bordas de 1px, em vez de
  sombras flutuantes.
- **Densidade de sala de controle.** Texto de 13px e controles de 32px, porque a tela mostra dados,
  não marketing.
- **Estado vazio sem borda tracejada.** Texto centrado com altura mínima.

O que **não** foi mantido: a paleta, a barra lateral, a aresta dos botões, o tile da navegação, o
selo chapado. Tudo isso é assinatura, e assinatura é do dono.

## Alternativas consideradas

- **shadcn/ui.** Padrão de fato, com os mesmos primitivos do Radix já estilizados. Rejeitado porque
  exige Tailwind, o que significaria reescrever todo o CSS e reverter a decisão Q-005, e porque o
  resultado seria estética shadcn, genérica por construção.
- **Mantine.** Boa para painéis, mas traz sistema de estilo e estética próprios, difíceis de dobrar
  para uma identidade de marca.
- **Adotar a linguagem do Coolify.** Tentado e descartado: é a identidade de outro produto.

## Tabela, cartão e seletor: quando cada um

Decidido em 2026-11-25, depois que a tela de Provedores nasceu em cartões e destoou do resto.

| Padrão | Quando | Onde |
|---|---|---|
| **Tabela** | linhas comparáveis, com os mesmos campos, que o usuário lê para comparar ou para achar a que está errada | hosts, projetos, usuários, provedores, modelos, chamadas |
| **Cartão** | conteúdo rico e de tamanho variável, que se lê um de cada vez | insights, notificações |
| **Seletor com busca** | escolher um item de uma lista que não cabe na tela | modelos do catálogo de um provedor |
| **Dropdown simples** | escolher entre poucas opções fixas dentro de um formulário | tipo de provedor, filtros |

A regra por trás: **a pergunta decide o formato.** "Qual destes está falhando?" e "qual vem
primeiro?" são perguntas comparativas, e comparação quer colunas alinhadas — um cartão obriga a
reler o mesmo rótulo em cada bloco. "O que aconteceu neste container?" é uma pergunta de leitura, e
aí o cartão ganha, porque o texto tem tamanho livre.

Corolários que valem repetir:

- **Uma tabela densa não comporta cinco botões por linha.** O que se consulta de relance vira coluna;
  o que se faz depois de decidir vai para um menu de ações. O interruptor é a exceção: fica na linha
  porque é o estado, não uma ação.
- **Detalhe abre na própria tabela**, como linha extra, não numa tela nova: sair da lista para ver um
  item custa o contexto dos vizinhos, que é justamente o que a lista dá.
- **Lista de três itens ainda é lista.** O seletor de tipo de provedor tem três opções hoje e
  continua sendo um dropdown, porque Anthropic, Azure e Ollama estão no roadmap e porque um
  formulário com três blocos grandes seguidos de campos pequenos fica desequilibrado.

## Empilhamento

Uma regra: **o que abre fica acima de quem abriu.** Daí a ordem `sticky < docked < modal < popup <
tooltip < toast`, com o popup **acima** do modal — um seletor dentro de um diálogo precisa pintar
sobre ele.

Isso não é teoria: a tela de Provedores quebrou exatamente aqui. O seletor de tipo vive dentro do
diálogo de cadastro e tinha `z-index: 60` contra os `71` do diálogo. Clicar abria a lista — o Radix
reportava `state=open`, com as três opções no DOM e medindo 156×98 — e ela pintava atrás do modal
opaco. Para quem usa, o efeito é indistinguível de um botão quebrado: a lista não expande.

Duas consequências que viraram código:

1. Nenhum componente escreve `z-index` com número. Todos usam `var(--z-*)`, porque valores soltos
   espalhados por quinze arquivos não têm como ser comparados entre si.
2. Um teste lê `tokens.css` e falha se a ordem inverter ou se alguém escrever um número à mão. Teste
   de componente não pega isto: `jsdom` não tem layout, então o elemento invisível passa como
   presente. O bug passou por 30 testes verdes.

## Marcas de terceiros

Os provedores de IA aparecem na interface com **os desenhos oficiais de cada marca**, não com
aproximações desenhadas por nós: o glifo da OpenRouter vem do material de marca deles, o símbolo da
OpenAI é o símbolo da OpenAI, e o da Amazon Bedrock é o ícone de serviço do AWS Architecture Icons.
Ficam inline como SVG, pela mesma razão que todo o resto: nada é buscado de CDN.

Três regras para elas, que não valem para os nossos próprios desenhos:

1. **Não se redesenha uma marca de terceiro.** Tamanho e cor mudam; a geometria, não.
2. **A cor é a que a marca publica.** A OpenRouter tem variante clara (`#7624F4`) e escura
   (`#C8FF00`) e nós honramos as duas via token; a OpenAI é monocromática por definição e segue o
   texto; a Bedrock usa o verde-azulado do ícone de serviço da AWS, que serve nos dois temas.
3. **Elas identificam, não endossam.** Aparecem só onde o usuário precisa saber com qual serviço
   está falando. São marcas registradas de seus donos, e o Lognix não é afiliado a nenhum deles.

## Consequências

- A decisão Q-005 continua valendo no essencial: **sem framework de utilitários CSS**. O que muda é
  que os componentes difíceis vêm do Radix em vez de serem caseiros.
- Onze pacotes `@radix-ui/*` entram no projeto. São pequenos e sem estilo.
- `window.confirm` e `<select>` nativo saem da base. Confirmação destrutiva agora é um diálogo que
  pode exigir digitar o nome do alvo.
- O tema claro funciona, mas o escuro é o desenho principal: é nele que a marca vive.
- A logo tem texto branco, então ganha um painel escuro próprio no tema claro.
