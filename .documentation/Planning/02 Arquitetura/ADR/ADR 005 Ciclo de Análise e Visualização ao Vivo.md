# ADR 005 — Ciclo de Análise e Visualização ao Vivo

**Status:** Aceito · **Data:** 2026-11-21

## Contexto

O produto precisa analisar logs continuamente para emitir alertas e abrir issues, e também permitir que
o usuário acompanhe logs em tempo real. A coleta pelo Alloy é contínua por natureza. A análise com IA
tem custo e não pode rodar linha a linha.

## Decisão

Dois modos distintos:

1. **Rotina de análise a cada 30 segundos.** O backend consulta o Loki pela janela dos últimos 30 s dos
   containers monitorados. Sobre essa janela roda, nesta ordem: agrupamento de padrões, detecção de
   erros, detecção de anomalias e, só quando houver trigger, IA e GitHub. Containers não monitorados
   **não têm logs coletados**: o Alloy os descarta no `discovery.relabel`. Eles aparecem só no inventário.
   *(Revisado em 2026-11-21: a versão original armazenava tudo e analisava só os selecionados.)*
2. **Visualização ao vivo.** A interface usa o tail do Loki para exibir linhas conforme chegam, sem
   esperar o ciclo. É modo de leitura, não dispara análise.

A coleta não tem ciclo: o Alloy envia continuamente ao Loki.

## Alternativas consideradas

- **Coletar a cada 30 s em vez de analisar a cada 30 s.** Incompatível com o Alloy e perderia linhas
  entre ciclos.
- **Analisar cada linha em tempo real.** Custo de IA proibitivo e desnecessário para o caso de uso.
- **Intervalo configurável desde a v1.** Adia-se. 30 s fixo na v1, configurável no roadmap.

## Consequências

- Latência máxima entre erro e início da análise: 30 s.
- A rotina precisa terminar em menos de 30 s para não acumular. Se atrasar, pula ciclo e registra.
- Seleção de containers monitorados é por host, parte do modelo de dados e da interface, e altera a config do Alloy a cada mudança.
- Container novo no host gera notificação. Padrão: não monitorado até o usuário optar.
- Gatilhos para IA precisam ser definidos com cuidado para controlar custo. Ver área 04.
