# Medição

Ferramentas para medir o Lognix. Nada aqui faz parte da instalação padrão.

## Harness do ADR 009

`backend/scripts/measure.py` sobe o app real contra um Postgres real, cria N hosts com SSH e
Docker simulados e M containers monitorados, e mede os critérios do ADR 009.

```bash
cd backend
docker run -d --name lognix-measure-pg -e POSTGRES_USER=lognix -e POSTGRES_PASSWORD=lognix \
  -e POSTGRES_DB=lognix_measure -p 5432:5432 postgres:16-alpine
.venv/bin/python scripts/measure.py --hosts 10 --containers 100 --lines 200 --rounds 3 \
  --api-seconds 30 --pause 30 --out medicao.json
```

Dois cenários de carga na API:

- **regime real**: um loop por container com a pausa de 30 s entre ciclos, como em produção;
- **saturação**: ciclos encadeados sem pausa nenhuma, muito além do que acontece na prática.

O critério do ADR 009 é avaliado no regime real; a saturação entra como informação.

## Prometheus e Grafana

```bash
docker compose -f docker-compose.yml -f measure/docker-compose.measure.yml up -d
```

Grafana em `http://localhost:3000`, Prometheus em `http://localhost:9090`. O Prometheus raspa
`/api/v1/metrics` do backend, e também Loki e Alloy. Consultas úteis:

```promql
histogram_quantile(0.95, sum(rate(lognix_cycle_duration_seconds_bucket[5m])) by (le, phase))
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
sum(rate(lognix_docker_proxy_requests_total[5m])) by (outcome)
lognix_tunnels
lognix_analysis_loops
```
