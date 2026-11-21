# ADR 001 — Loki como Armazenamento de Logs

**Status:** Aceito · **Data:** 2026-11-21

## Contexto

O Alloy precisa gravar os logs coletados em algum lugar, e o backend, a interface e a IA precisam
consultá-los por host, container e janela de tempo. O padrão de acesso dominante é "mostre o container X
nos últimos N minutos", não busca de texto livre em todo o histórico.

## Decisão

Grafana Loki é o único armazenamento de logs. Roda como container ao lado do Lognix. O Alloy grava via
`loki.write`. O backend consulta via LogQL e tail. O Postgres do Lognix guarda apenas metadados,
análises, insights, alertas e issues, nunca linhas de log.

## Alternativas consideradas

- **PostgreSQL para tudo.** Mais simples no início, mas obriga a reimplementar retenção, compressão e
  streaming, e não escala em volume de log.
- **ClickHouse.** Excelente para analítica, mas sem integração nativa com Alloy e com operação mais pesada.
- **OpenSearch / Elasticsearch.** Busca full-text, porém custo de operação e memória muito acima do
  necessário para o caso de uso.

## Consequências

- Retenção, compactação e deleção são nativas do Loki.
- Busca full-text em janelas longas é lenta. Aceito, porque não é o caso de uso.
- Labels precisam ser poucos e de baixa cardinalidade. Nome de container e host são aceitáveis; IDs de
  requisição não.
- O frontend pode usar o tail do Loki para a visualização ao vivo sem passar pelo backend em cada linha.
