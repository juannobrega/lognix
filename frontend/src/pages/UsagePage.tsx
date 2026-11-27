import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { AiCall, AiSettings, ProviderUsage, Usage, UsageBucket } from '../api/types'
import { Alert } from '../components/Alert'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { dateTime, tokens, usd } from '../components/format'
import { SkeletonRows } from '../components/Skeleton'
import { Stat, StatGrid } from '../components/Stat'
import { Tooltip } from '../ui/Tooltip'
import { TRIGGER_LABEL } from '../insights/severity'
import { ProviderIcon } from '../providers/icons'

function BucketTable({ title, rows, labels }: { title: string; rows: UsageBucket[]; labels?: Record<string, string> }) {
  if (rows.length === 0) return null
  return (
    <section className="card">
      <div className="card-header">
        <h2>{title}</h2>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>{title}</th>
            <th className="right">Chamadas</th>
            <th className="right">Tokens</th>
            <th className="right">Custo</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td>{labels?.[r.key] ?? r.key}</td>
              <td className="right">{r.calls}</td>
              <td className="right">{tokens(r.input_tokens + r.output_tokens)}</td>
              <td className="right">{usd(r.cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function ProviderTable({ rows, paused }: { rows: ProviderUsage[]; paused: Record<string, string> }) {
  if (rows.length === 0) return null
  return (
    <section className="card">
      <div className="card-header">
        <h2>Provedores</h2>
        <Link to="/ai/providers" style={{ fontSize: 'var(--text-sm)' }}>
          Configurar cadeia
        </Link>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Provedor</th>
            <th className="right">Chamadas</th>
            <th className="right">Sucesso</th>
            <th className="right">Fallbacks</th>
            <th className="right">Latência média</th>
            <th className="right">p95</th>
            <th className="right">Custo</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const until = r.provider_id ? paused[r.provider_id] : undefined
            return (
              <tr key={r.provider_id ?? r.name}>
                <td>
                  <span className="row" style={{ gap: 7, flexWrap: 'nowrap' }}>
                    <ProviderIcon kind={r.kind} width={16} height={16} />
                    {r.name || r.kind}
                    {until && (
                      <Tooltip content={`Pausado até ${dateTime(until)} por limite de uso. A cadeia segue para o próximo.`}>
                        <span style={{ color: 'var(--warn)', fontSize: 'var(--text-meta)', fontWeight: 600 }}>PAUSADO</span>
                      </Tooltip>
                    )}
                  </span>
                </td>
                <td className="right">{r.calls}</td>
                <td className="right" style={{ color: r.errors > 0 ? 'var(--warn)' : undefined }}>
                  {(r.success_rate * 100).toFixed(0)}%
                  {r.errors > 0 && <span className="muted"> ({r.errors} erro{r.errors > 1 ? 's' : ''})</span>}
                </td>
                <td className="right muted">{r.fallbacks}</td>
                <td className="right muted">{(r.avg_latency_ms / 1000).toFixed(1)}s</td>
                <td className="right muted">{(r.p95_latency_ms / 1000).toFixed(1)}s</td>
                <td className="right">{usd(r.cost_usd)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

export function UsagePage() {
  const [onlyErrors, setOnlyErrors] = useState(false)
  const ai = useQuery({ queryKey: ['settings', 'ai'], queryFn: () => api<AiSettings>('/settings/ai') })
  const usage = useQuery({ queryKey: ['usage'], queryFn: () => api<Usage>('/settings/usage'), refetchInterval: 30_000 })
  const calls = useQuery({
    queryKey: ['usage', 'calls', onlyErrors],
    queryFn: () => api<AiCall[]>(`/settings/usage/calls?limit=100&only=${onlyErrors ? 'errors' : 'all'}`),
    refetchInterval: 30_000,
  })

  if (usage.isError) return <ErrorState error={usage.error} onRetry={() => void usage.refetch()} />
  const u = usage.data
  if (!u) return <div className="card"><SkeletonRows rows={5} /></div>

  return (
    <div className="stack" style={{ maxWidth: 1000 }}>
      {Object.keys(u.paused_providers).length > 0 && (
        <Alert
          kind="warn"
          message={`${Object.keys(u.paused_providers).length} provedor(es) pausado(s) por limite de uso.`}
          action="A cadeia segue para o próximo. Se todos pausarem, as ocorrências ficam em Insights › Sem análise."
        />
      )}

      <section className="card">
        <div className="card-header">
          <h2>Consumo de IA</h2>
          <span className="muted" style={{ fontSize: 'var(--text-sm)' }}>
            {ai.data
              ? ai.data.active
                ? `IA ligada · ${ai.data.providers_ready} provedor(es) na cadeia`
                : ai.data.configured
                  ? 'IA desligada'
                  : 'nenhum provedor pronto'
              : '—'}
          </span>
        </div>
        <div className="card-body">
          <StatGrid>
            <Stat value={usd(u.today.cost_usd)} label="Hoje" hint={`${u.today.calls} chamadas`} />
            <Stat value={usd(u.last_7d.cost_usd)} label="7 dias" hint={`${u.last_7d.calls} chamadas`} />
            <Stat value={usd(u.last_30d.cost_usd)} label="30 dias" hint={`${u.last_30d.calls} chamadas`} />
            <Stat value={usd(u.total.cost_usd)} label="Total" hint={`${tokens(u.total.input_tokens + u.total.output_tokens)} tokens`} />
            <Stat
              value={u.failures}
              label="Chamadas com erro"
              tone={u.failures > 0 ? 'error' : 'ok'}
              hint={u.schema_retries > 0 ? `${u.schema_retries} retry de formato` : 'nenhum retry'}
            />
            <Stat
              value={u.fallbacks}
              label="Caíram para o fallback"
              tone={u.fallbacks > 0 ? 'warn' : 'ok'}
              hint={u.fallbacks > 0 ? 'o provedor anterior recusou' : 'nenhuma troca de provedor'}
            />
            <Stat value={`${(u.avg_latency_ms / 1000).toFixed(1)}s`} label="Latência média" hint="da chamada ao insight pronto" />
          </StatGrid>
        </div>
      </section>

      <ProviderTable rows={u.by_provider} paused={u.paused_providers} />

      {u.total.calls === 0 ? (
        <EmptyState title="Nenhuma chamada de IA ainda">
          <p>
            {ai.data?.active
              ? 'A IA está ativa. A primeira chamada acontece quando um trigger disparar num projeto monitorado.'
              : ai.data?.configured
                ? 'Há provedor pronto, mas a IA está desligada. Ative em Configurações › IA.'
                : 'Cadastre um provedor em Configurações › Provedores para começar.'}
          </p>
        </EmptyState>
      ) : (
        <>
          <BucketTable title="Modelo" rows={u.by_model} />
          <BucketTable title="Projeto" rows={u.by_project} />
          <BucketTable title="Trigger" rows={u.by_trigger} labels={TRIGGER_LABEL} />
          <BucketTable title="Dia" rows={u.by_day} />
        </>
      )}

      <section className="card">
        <div className="card-header">
          <h2>Chamadas</h2>
          <div className="segmented" role="group" aria-label="Filtrar chamadas">
            <button onClick={() => setOnlyErrors(false)} aria-pressed={!onlyErrors}>
              Todas
            </button>
            <button onClick={() => setOnlyErrors(true)} aria-pressed={onlyErrors}>
              Só erros
            </button>
          </div>
        </div>
        {calls.isPending ? (
          <SkeletonRows rows={3} />
        ) : calls.data?.length === 0 ? (
          <p className="muted card-body" style={{ margin: 0 }}>
            {onlyErrors ? 'Nenhuma chamada com erro.' : 'Nenhuma chamada ainda.'}
          </p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Quando</th>
                <th>Projeto</th>
                <th>Provedor</th>
                <th>Modelo</th>
                <th className="right">Tokens</th>
                <th className="right">Custo</th>
                <th className="right">Latência</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {calls.data?.map((c) => (
                <tr key={c.id}>
                  <td className="muted">{dateTime(c.created_at)}</td>
                  <td>{c.container_name ?? '—'}</td>
                  <td>
                    <span className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
                      <ProviderIcon kind={c.provider} width={14} height={14} />
                      {c.provider_name || c.provider}
                      {c.fell_back && (
                        <Tooltip content={`Tentativa ${c.attempt + 1}: os provedores anteriores da cadeia recusaram.`}>
                          <span style={{ color: 'var(--warn)', fontSize: 'var(--text-meta)', fontWeight: 600 }}>FALLBACK</span>
                        </Tooltip>
                      )}
                    </span>
                  </td>
                  <td className="mono">{c.model}</td>
                  <td className="right">{tokens(c.input_tokens + c.output_tokens)}</td>
                  <td className="right">{usd(c.cost_usd)}</td>
                  <td className="right muted">{(c.latency_ms / 1000).toFixed(1)}s</td>
                  <td style={{ color: c.status === 'error' ? 'var(--error)' : 'var(--ok)' }}>
                    {c.status === 'error' ? (c.error ?? 'erro').slice(0, 80) : c.schema_retry ? 'ok (retry)' : 'ok'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Como o custo é contado</h2>
        </div>
        <div className="card-body">
          <p className="muted" style={{ marginTop: 0 }}>
            Cada tentativa registra provedor, modelo, tokens, custo, latência e o trigger que a originou. O custo vem da resposta do
            provedor quando ele informa; caso contrário é estimado pelo preço cadastrado naquele modelo, em Provedores › Modelos. Modelo sem
            preço cadastrado e provedor que não informa custo somam zero — o que aparece como consumo de graça, não como erro.
          </p>
          <p className="muted" style={{ marginBottom: 0 }}>
            Não há orçamento com bloqueio nesta versão. Um projeto com erro contínuo gera um insight por ciclo, porque ainda não há
            deduplicação. Para conter, marque o padrão como ignorado na aba Padrões do projeto, ou desligue a IA.{' '}
            <Link to="/insights">Ver insights</Link>
          </p>
        </div>
      </section>
    </div>
  )
}
