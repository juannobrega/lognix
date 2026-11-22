import { Link } from 'react-router-dom'
import type { TriggerFired } from '../api/types'
import { EmptyState } from '../components/EmptyState'

const label: Record<TriggerFired['type'], string> = { error: 'erro', docker_event: 'evento Docker', anomaly: 'anomalia', manual: 'manual' }
const tone: Record<TriggerFired['type'], string> = { error: 'var(--sev-high)', docker_event: 'var(--sev-critical)', anomaly: 'var(--sev-medium)', manual: 'var(--sev-info)' }

export function TriggerList({ triggers, showProject = false }: { triggers: TriggerFired[]; showProject?: boolean }) {
  if (triggers.length === 0) return <EmptyState title="Nenhuma ocorrência" />
  return (
    <div className="card">
      <ul className="list">
        {triggers.map((t) => (
          <li key={t.id}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="row" style={{ gap: 10 }}>
                <span style={{ fontWeight: 700, color: tone[t.type], fontSize: 'var(--text-xs)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {label[t.type]}
                </span>
                {showProject && t.container_name && (
                  <Link to={`/projects/${t.container_id}`} style={{ fontWeight: 500 }}>
                    {t.container_name}
                  </Link>
                )}
                {showProject && t.host_name && <span className="muted">{t.host_name}</span>}
                <span>{t.note}</span>
              </span>
              <span className="muted" style={{ fontSize: 'var(--text-sm)' }}>
                {new Date(t.fired_at).toLocaleString('pt-BR')} · janela {new Date(t.window_start).toLocaleTimeString('pt-BR')} →{' '}
                {new Date(t.window_end).toLocaleTimeString('pt-BR')}
              </span>
            </div>
            {t.sample_lines.length > 0 && (
              <details style={{ marginTop: 6 }}>
                <summary className="muted" style={{ cursor: 'pointer', fontSize: 'var(--text-sm)' }}>
                  {t.sample_lines.length} linha(s) de erro
                </summary>
                <pre
                  style={{
                    margin: '6px 0 0',
                    background: 'var(--log-bg)',
                    color: 'var(--log-error-fg)',
                    padding: 'var(--space-3)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: 'var(--text-xs)',
                    overflowX: 'auto',
                    maxHeight: 240,
                  }}
                >
                  {t.sample_lines.map((l) => l.line).join('\n')}
                </pre>
              </details>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
