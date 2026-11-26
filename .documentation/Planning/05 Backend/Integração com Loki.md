# Integração com Loki

**Status:** Aprovado em 2026-11-21 · **Atualizado:** 2026-11-21

Único módulo que fala com o Loki: `lognix/loki/`. Base: ADR 001, ADR 004.

## 1. Operações

| Operação | API do Loki | Uso |
|---|---|---|
| Consulta de janela | `GET /loki/api/v1/query_range` | ciclo de análise, histórico na interface |
| Tail | WebSocket `/loki/api/v1/tail` | logs ao vivo |
| Labels e valores | `GET /loki/api/v1/labels`, `/label/{name}/values` | diagnóstico, tela Sistema |
| Deleção | `POST /loki/api/v1/delete` | apagar host de fato. Exige deleção habilitada no Loki |
| Saúde | `GET /ready` | health |

## 2. Seletores

Sempre por `container_id`, o uuid do Lognix. Nunca por nome, que pode mudar.

| Caso | LogQL |
|---|---|
| Ciclo | `{container_id="<uuid>"}` com `start`/`end` da janela, `direction=forward`, `limit=5000` |
| Histórico com filtro de texto | `{container_id="<uuid>"} |= "texto"` |
| Só stderr | `{container_id="<uuid>", stream="stderr"}` |
| Nível em log JSON | `{container_id="<uuid>"} | json | level="error"` |
| Taxa de linhas, anomalia de volume | `count_over_time({container_id="<uuid>"}[1m])` |

Nível por regex **não** é feito em LogQL. O classificador em Python é a única implementação, para que
a regra seja uma só e testada.

## 3. Paginação na janela

Se a janela do ciclo devolver 5 000 linhas, o ciclo continua consultando a partir do timestamp da
última linha até esgotar, com teto de 50 000 linhas por ciclo. Acima do teto: registra
`AnalysisRun.status = ok` com marca `truncated`, gera notificação de volume excessivo, e o próximo
ciclo começa de onde parou. Container com esse volume sustentado é candidato a não ser monitorado.

## 4. Tail

- Um tail por projeto, aberto no primeiro espectador, fechado 30 s após o último sair.
- Linhas são repassadas aos clientes WebSocket sem transformação além de JSON.
- Se o tail cair, o backend reabre com `start` igual ao último timestamp recebido.

## 5. Labels

Definidos no Modelo de Dados seção 3. O módulo valida que a config gerada do Alloy só produz esses
labels. Qualquer label fora da lista é erro de geração.

## 6. Configuração do Loki no compose

- Modo monolítico, armazenamento em filesystem, volume `loki-data`.
- `retention_period` vindo de `LOKI_RETENTION_DAYS`.
- Compactor com deleção habilitada, para o apagar de host.
- Sem autenticação: o Loki só é alcançável na rede interna do compose. Nunca expor a porta.
- Limites: `max_query_length` 16 dias, `max_entries_limit_per_query` 5 000.
