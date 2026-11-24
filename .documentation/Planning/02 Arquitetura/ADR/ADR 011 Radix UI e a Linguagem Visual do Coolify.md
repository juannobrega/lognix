# ADR 011 — Radix UI e a Linguagem Visual do Coolify

**Status:** Aceito · **Data:** 2026-11-24

## Contexto

A interface construída até a 0.8.0 funcionava, mas parecia amadora. O dono do projeto foi direto:
"está muito feio, componentes mal desenhados". O Lognix é código aberto e vai ser divulgado; a
primeira impressão de quem abre a tela importa tanto quanto o que o backend faz.

Dois problemas distintos estavam misturados:

1. **Falta de linguagem visual.** O design system da 0.8.0 era genérico: cinzas neutros, azul
   padrão, sombras em cartões, espaçamentos de 16px. Nada errado, nada memorável.
2. **Componentes caseiros onde não deviam ser.** `<select>` nativo, `window.confirm`, abas feitas
   com botões, nenhum tooltip, nenhum diálogo. São justamente os componentes difíceis de acertar em
   acessibilidade, e os que mais denunciam amadorismo.

## Decisão

**Linguagem visual: a do Coolify.** O dono do projeto a citou como referência, e ela resolve bem o
problema de um painel de operação: denso, calmo, legível em sessões longas. Os valores vêm do
`DESIGN.md` do projeto, e o princípio central é **camadas, não caixas**:

| | |
|---|---|
| Superfícies | canvas `#0a0a0a` → painel `#121212` → card → well → controle |
| Acento | roxo `#6b16ed`, com gradiente `#7317ff` → `#5a12c7` e aresta `#4a0fa3` |
| Barra lateral | `#120e1a`, com leve tom roxo |
| Tipografia | Geist Sans e Geist Mono, 11px meta, 13px interface, 14px campos, 24px títulos |
| Pesos | 500 em rótulos e botões, 600 em títulos. Sem 700 |
| Controles | 32px de altura, raio 8px |
| Profundidade | aresta inferior de 2px que levanta 1px no hover e afunda ao clicar |
| Selos de estado | ponto de 6px e texto. Sem borda, sem fundo, sem padding |
| Estado vazio | texto centrado, altura mínima. Sem borda tracejada |

A fonte é servida pelo próprio pacote, via `@fontsource-variable`, porque a política de segurança
de conteúdo do nginx bloqueia CDNs.

**Componentes: Radix UI primitives, com CSS Modules.** Radix dá o comportamento e a acessibilidade
dos componentes difíceis, sem impor estilo: diálogo com foco preso e `Esc`, select navegável por
teclado, tooltip com atraso, switch, abas. O estilo continua nosso, em CSS Modules, como o ADR da
Stack decidiu.

## Alternativas consideradas

- **shadcn/ui.** É o padrão de fato: os mesmos primitivos do Radix, já estilizados, copiados para o
  projeto. Rejeitado porque exige Tailwind, o que significaria reescrever todo o CSS existente e
  reverter a decisão Q-005. O ganho seria estética pronta, mas estética genérica: o alvo aqui é
  parecer com o Coolify, não com um projeto shadcn.
- **Mantine.** Completo e bom para painéis, mas traz um sistema de estilo próprio e uma estética
  própria, difícil de dobrar para a linguagem do Coolify.
- **Continuar sem biblioteca.** O que havia. Reescrever select, diálogo e tooltip acessíveis à mão
  é trabalho que já foi feito melhor por outros, e errar acessibilidade em silêncio é fácil.

## Consequências

- A decisão Q-005 continua valendo no essencial: **sem framework de utilitários CSS**. O que muda é
  que os componentes difíceis passam a vir do Radix em vez de serem caseiros.
- Onze pacotes `@radix-ui/*` entram no `package.json`. São pequenos e sem estilo; o `bundle` cresceu
  cerca de 75 KB comprimidos, aceitável para um painel que fica aberto.
- `window.confirm` e `<select>` nativo saem da base. Confirmação de ação destrutiva agora é um
  diálogo que pode exigir digitar o nome do alvo.
- O tema claro existe e funciona, mas o escuro é o desenho principal: é nele que a linguagem do
  Coolify foi pensada.
- A logo tem texto branco, então ganha um painel escuro próprio no tema claro.
