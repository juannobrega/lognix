# Monitoramento Kubernetes

**Status:** Reservado para v2 · **Atualizado:** 2026-11-21

Este documento **não** planeja o suporte a Kubernetes. Registra só as restrições que a v1 precisa
respeitar para que o suporte seja possível sem reescrita.

## Restrições para a v1

| Restrição | Onde se aplica |
|---|---|
| `Host.runtime` é enum, hoje só `docker`. Nada no código assume Docker fora dos módulos de coleta Docker | Modelo de Dados, backend |
| A interface chama de "projeto" o que o banco chama de `Container`. Em Kubernetes um projeto será um deployment ou pod. O nome na interface não pode vazar `container` como conceito fixo | Frontend |
| Labels no Loki usam `host` e `container`. Em Kubernetes serão `cluster`, `namespace`, `pod`, `container`. O cliente Loki do backend não pode ter a lista de labels fixa em código | Backend, Alloy |
| Gerador de config do Alloy é por host e por runtime. Kubernetes usará `discovery.kubernetes` e `loki.source.kubernetes`, outro gerador | Backend |
| Eventos Docker viram `DockerEvent`. Em Kubernetes serão eventos de pod. A entidade pode ser renomeada para `WorkloadEvent` já na v1 | Modelo de Dados |
| Conexão por SSH e `docker.sock`. Em Kubernetes será kubeconfig e API server. O supervisor de túneis não pode ser a única forma de "conexão" no código | Backend |

## O que muda no modelo em v2, previsão

- Entidade `Cluster` ao lado de `Host`.
- `Workload` como tabela genérica, com `Container` como caso Docker.
- Alloy pode continuar ao lado do Lognix, lendo a API do cluster via kubeconfig, sem instalar nada
  no cluster. Ou pode ser instalado como DaemonSet, modelo padrão da Grafana. Decisão em v2.
