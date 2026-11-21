# ADR 004 — Fronteiras entre Alloy, Loki e Backend

**Status:** Aceito · **Data:** 2026-11-21

## Contexto

Com Alloy, Loki e backend Python no mesmo sistema, é preciso definir quem faz o quê para não duplicar
trabalho nem reimplementar o que as ferramentas já fazem.

## Decisão

| Responsabilidade | Dono | Observação |
|---|---|---|
| Túneis SSH | Backend | Supervisor de túneis |
| Somente leitura na Docker API | Backend | Proxy do ADR 003 |
| Descobrir containers para fins de log | Alloy | `discovery.docker` por host |
| Ler logs e enviar ao Loki | Alloy | `loki.source.docker` + `loki.write` |
| Enriquecer logs com labels | Alloy | `discovery.relabel`, `loki.process` |
| Armazenar e consultar logs | Loki | LogQL, tail, retenção |
| Inventário com estado, eventos, inspeção | Backend | Docker API via proxy |
| Gerar e recarregar config do Alloy | Backend | Um bloco por host, `/-/reload` |
| Ciclo de análise por container | Backend | Consulta Loki, nunca o Docker |
| Padrões, anomalias, IA, GitHub | Backend | |
| Interface, logs ao vivo | Frontend | Tail do Loki, dados do backend |

O backend **nunca lê linhas de log pela Docker API**. Logs vêm sempre do Loki. A Docker API serve só
para metadados e eventos.

## Alternativas consideradas

- **Backend descobre containers lendo labels do Loki.** Insuficiente: container mudo não aparece, e não
  há estado nem eventos.
- **Backend lê alvos descobertos pela API de debug do Alloy.** API interna, sem garantia de estabilidade.
- **Alloy também coleta eventos Docker.** Não existe componente para isso.

## Consequências

- O Alloy pode ser substituído ou atualizado sem tocar no backend, desde que grave no Loki com os mesmos labels.
- O Loki é a única fonte de verdade dos logs. Postgres guarda só o que o Lognix produz.
- Eventos Docker, como restart e OOM, são capturados pelo backend e viram entidades próprias, essenciais
  para o diagnóstico de causa raiz.
