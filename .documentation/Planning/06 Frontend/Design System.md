# Design System

**Status:** Aprovado em 2026-11-24. Primeiro passe aplicado em 2026-11-22 · **Atualizado:** 2026-11-21

> **Nota de 2026-11-26.** A interface passou por dois redesenhos depois deste documento: a
> identidade própria (ADR 011) e a passagem de cartão para tabela nas telas de lista, mais o
> sidebar com grupos que abrem e a tela de entrada com cards. O que está descrito abaixo é a
> intenção de origem, que em boa parte sobreviveu; onde divergir, valem o
> [ADR 011](../02%20Arquitetura/ADR/ADR%20011%20Identidade%20Visual%20do%20Lognix.md) e o código.


Mínimo necessário para a interface ser consistente. Sem biblioteca externa.

## 1. Tokens

Definidos como variáveis CSS em `:root`, com tema escuro em `[data-theme="dark"]` e `prefers-color-scheme`.

| Grupo | Tokens |
|---|---|
| Cor de superfície | `--bg`, `--bg-elevated`, `--border` |
| Texto | `--fg`, `--fg-muted` |
| Ação | `--accent`, `--accent-fg` |
| Severidade | `--sev-critical`, `--sev-high`, `--sev-medium`, `--sev-low`, `--sev-info` |
| Estado | `--ok`, `--warn`, `--error`, `--neutral` |
| Espaço | `--space-1` a `--space-8`, escala de 4 px |
| Raio | `--radius-sm`, `--radius-md` |
| Tipografia | `--font-ui` sistema, `--font-mono` para logs; tamanhos `--text-xs` a `--text-xl` |

Cores de severidade e estado têm contraste AA em ambos os temas e não dependem só da cor: sempre
acompanhadas de texto ou ícone.

## 2. Tema

Claro e escuro desde a 0.1.0. Preferência do sistema por padrão, alternável no rodapé da barra, salva
em `localStorage`. Logs em fundo escuro por padrão nos dois temas, por legibilidade.

## 3. Layout

- Barra lateral fixa de 220 px, colapsável para 56 px com ícones.
- Conteúdo com largura máxima de 1 400 px, exceto logs, que ocupam a largura toda.
- Responsivo até 1 024 px. Abaixo disso, barra vira menu e tabelas viram cartões. Celular não é alvo da v1.

## 4. Tipografia

- Interface: fonte do sistema.
- Logs e código: monoespaçada do sistema, 13 px, altura de linha 1,5.
- Sem fontes externas: nada carregado de CDN.

## 4.1 Aplicado em 2026-11-22

- Tokens completos em `tokens.css`, incluindo variantes `*-soft` para fundos de selo e alerta.
- Classes utilitárias globais: `.page-header`, `.card`, `.table`, `.list`, `.kv`, `.tabs`, `.segmented`.
- Barra lateral com ícones SVG inline, avatar com iniciais, contador de notificações.
- Selos de estado com fundo suave e ponto colorido. Botões com tamanhos `md` e `sm`.
- Páginas de host e projeto reorganizadas em abas.

## 4.2 Aplicado na 0.8.0

- Componentes novos: `Skeleton` e `SkeletonRows` para carregamento, `Stat` e `StatGrid` para números,
  `Toast` com provider e `useToast`, `ErrorState` com ação de nova tentativa.
- Formatações compartilhadas em `components/format.ts`, fora dos módulos de componente por causa do
  Fast Refresh: `compact`, `bytes`, `duration`.
- Toda lista tem três estados tratados: carregando com esqueleto, vazio com explicação e ação, erro
  com mensagem e botão.
- Ações que mudam estado dão retorno por toast, não só por texto na tela.
- `prefers-reduced-motion` desliga as animações de esqueleto e de toast.

## 4.3 Identidade, 2026-11-24

A interface passou a ter identidade própria, derivada da marca: azul elétrico, ciano e violeta,
com as barras verticais do símbolo como motivo. Decisão, valores e as três assinaturas visuais em
[ADR 011](../02%20Arquitetura/ADR/ADR%20011%20Identidade%20Visual%20do%20Lognix.md). Os tokens desta
página valem como esqueleto; os valores em vigor estão em `src/styles/tokens.css`.

As assinaturas: **barra de sinal** no item ativo e no cartão em hover, **botão com brilho interno**
em vez de aresta de profundidade, **ponto com halo** nos estados. Mais o fio de marca no topo dos
blocos que lideram a tela e o `SparkBars` para séries curtas.

Componentes do Radix em `src/ui/`: `Select`, `ConfirmDialog`, `Tooltip`, `Switch`. Saíram da base o
`<select>` nativo e o `window.confirm`.

## 5. Identidade

Nome Lognix, sem logotipo elaborado na v1: marca em texto. Cor de destaque única. Decisão de cor e
eventual logotipo ficam para antes do 1.0.0, não bloqueiam nada.
