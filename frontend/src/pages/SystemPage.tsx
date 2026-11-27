import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { SystemInfo } from '../api/types'
import { Alert } from '../components/Alert'
import { bytes, duration } from '../components/format'
import { UpdateCard } from './UpdateCard'

const COUNT_LABELS: Record<string, string> = {
  hosts: 'Hosts',
  hosts_connected: 'Hosts conectados',
  containers: 'Containers',
  monitored: 'Monitorados',
  excluded: 'Excluídos',
  patterns: 'Padrões',
  analysis_runs: 'Ciclos de análise',
  triggers: 'Ocorrências',
  triggers_unanalyzed: 'Sem análise',
}

const LOOP_LABELS: Record<string, string> = { tunnels: 'Túneis SSH', analysis: 'Ciclos de análise', log_tails: 'Tails de log' }

export function SystemPage() {
  const sys = useQuery({ queryKey: ['system'], queryFn: () => api<SystemInfo>('/system'), refetchInterval: 15_000 })
  const s = sys.data
  if (!s) return <p className="muted">Carregando…</p>
  const tunnels = s.loops.find((l) => l.kind === 'tunnels')
  const degraded = Object.entries(s.components).filter(([, c]) => !c.ok)

  return (
    <div className="stack">
      {degraded.length > 0 && (
        <Alert kind="error" message={`Componentes com problema: ${degraded.map(([k]) => k).join(', ')}.`} action="Veja os detalhes abaixo." />
      )}
      <div className="grid-2">
        <section className="card">
          <div className="card-header">
            <h2>Instalação</h2>
          </div>
          <div className="card-body">
            <dl className="kv">
              <dt>Versão</dt>
              <dd className="mono">v{s.version}</dd>
              <dt>No ar há</dt>
              <dd>{duration(s.uptime_seconds)}</dd>
              <dt>Retenção de logs</dt>
              <dd>{s.retention_days} dias</dd>
              <dt>Intervalo entre ciclos</dt>
              <dd>{s.analysis_interval_seconds} s</dd>
              <dt>Requisições bloqueadas pelo proxy</dt>
              <dd style={{ color: s.proxy_rejected_total > 0 ? 'var(--warn)' : undefined }}>{s.proxy_rejected_total}</dd>
            </dl>
          </div>
        </section>
        <UpdateCard />
        <section className="card">
          <div className="card-header">
            <h2>Componentes</h2>
          </div>
          <ul className="list">
            {Object.entries(s.components).map(([name, c]) => (
              <li key={name} className="row" style={{ justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 500 }}>{name}</span>
                <span className="row" style={{ gap: 8 }}>
                  {c.detail && <span className="muted mono">{c.detail}</span>}
                  <span style={{ color: c.ok ? 'var(--ok)' : 'var(--error)', fontWeight: 600 }}>{c.ok ? 'ok' : 'indisponível'}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="card">
        <div className="card-header">
          <h2>Números</h2>
        </div>
        <div className="card-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 'var(--space-4)' }}>
          {Object.entries(s.counts).map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700 }}>{v.toLocaleString('pt-BR')}</div>
              <div className="muted" style={{ fontSize: 'var(--text-sm)' }}>{COUNT_LABELS[k] ?? k}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Processos em execução</h2>
          <span className="muted" style={{ fontSize: 'var(--text-sm)' }}>{s.loops.map((l) => `${LOOP_LABELS[l.kind] ?? l.kind}: ${l.count}`).join(' · ')}</span>
        </div>
        {tunnels && tunnels.detail.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Host</th>
                <th>Estado</th>
                <th className="right">Reconexões</th>
                <th className="right">Eventos</th>
                <th className="right">Reaberturas</th>
                <th>Último erro</th>
              </tr>
            </thead>
            <tbody>
              {tunnels.detail.map((t) => (
                <tr key={String(t.host)}>
                  <td style={{ fontWeight: 500 }}>{String(t.host)}</td>
                  <td style={{ color: t.connected ? 'var(--ok)' : 'var(--error)' }}>{String(t.status)}</td>
                  <td className="right">{String(t.reconnect_attempts)}</td>
                  <td className="right">{String(t.events_seen)}</td>
                  <td className="right">{String(t.stream_restarts)}</td>
                  <td className="muted" style={{ fontSize: 'var(--text-sm)' }}>{t.last_error ? String(t.last_error) : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Disco</h2>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Caminho</th>
              <th className="right">Usado</th>
              <th className="right">Livre</th>
              <th className="right">Total</th>
            </tr>
          </thead>
          <tbody>
            {s.volumes.map((v) => (
              <tr key={v.path}>
                <td className="mono">{v.path}</td>
                <td className="right">{bytes(v.used_bytes)}</td>
                <td className="right">{bytes(v.free_bytes)}</td>
                <td className="right">{bytes(v.total_bytes)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
