# Componentes

**Status:** Aprovado em 2026-11-24 · **Atualizado:** 2026-11-21

Biblioteca própria, sem framework de UI. CSS Modules. Cada componente: pasta com `.tsx`, `.module.css`,
teste e história curta em Markdown.

## 1. Base

| Componente | Notas |
|---|---|
| `Button` | variantes primária, secundária, perigo, fantasma; estados carregando e desabilitado |
| `Input`, `Textarea`, `Select`, `Checkbox`, `Toggle` | com rótulo, ajuda e erro acessíveis |
| `SecretInput` | mostra mascarado, botão revelar, usado para chaves e senhas |
| `Badge` | severidade, estado de host, estado de container, tipo de projeto |
| `Card`, `Panel` | contêineres de seção |
| `Table` | ordenável, com virtualização opcional |
| `Tabs` | com rota sincronizada |
| `Modal`, `ConfirmDialog` | confirmação destrutiva exige digitar o nome do alvo |
| `Toast` | sucesso, erro, info |
| `EmptyState` | ícone, título, explicação, ação |
| `Skeleton` | carregamento |
| `Tooltip`, `Dropdown` | |

## 2. Domínio

| Componente | Usado em |
|---|---|
| `HostStatus` | lista de hosts, cabeçalho de host, painel |
| `ValidationSteps` | cadastro de host, seis etapas com estado e ação |
| `ContainerPicker` | seleção de monitorados, agrupado por projeto Compose |
| `LogViewer` | logs ao vivo e histórico, virtualizado, destaque de erro, permalink |
| `LogLine` | uma linha, com timestamp, stream, nível, texto |
| `PatternTable` | aba padrões |
| `EventTimeline` | eventos Docker e de host |
| `InsightCard` | listas de insights |
| `InsightDetail` | tela de insight |
| `EvidenceList` | evidências com link para o log |
| `SeverityBadge`, `ConfidenceBadge` | selo de baixa confiança abaixo de 0,4 |
| `NotificationItem` | com ações inline |
| `ExecutorPanel` | painel lateral de análises em andamento |
| `UsageSummary`, `UsageChart` | tela de consumo |
| `ModelPicker` | seletor de modelo com busca e preços |
| `SensitiveDataNotice` | aviso fixo de dados sensíveis |
| `VersionFooter` | versão e estado da IA na barra lateral |

## 3. Regras

- Nenhum componente faz requisição. Dados chegam por props, de hooks na tela.
- Acessibilidade: foco visível, rótulos, contraste mínimo AA, navegação por teclado no `LogViewer`.
- Textos em português, centralizados em um módulo de strings para facilitar internacionalização futura.
- Ícones: um único conjunto, SVG inline, sem fonte de ícones.
