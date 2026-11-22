import type { DockerEvent, HostEvent } from '../api/types'

const labels: Record<string, string> = {
  connected: 'conectado',
  disconnected: 'desconectado',
  new_container: 'novo container',
  container_removed: 'container removido',
  inventory_synced: 'inventário sincronizado',
  events_stream_restarted: 'stream de eventos reaberto',
  error: 'erro',
  start: 'iniciou',
  die: 'encerrou',
  oom: 'OOM kill',
  restart: 'reiniciou',
  kill: 'kill',
  stop: 'parado',
  pause: 'pausado',
  unpause: 'retomado',
  health_status: 'healthcheck',
  destroy: 'destruído',
  redeploy: 'redeploy',
}

const critical = new Set(['die', 'oom', 'disconnected', 'error', 'health_status'])

function describe(e: DockerEvent | HostEvent): string {
  const a = e.attributes as Record<string, string | undefined>
  if ('previous_image' in e && e.type === 'redeploy') return `${e.previous_image ?? '?'} → ${e.new_image ?? '?'}`
  if ('exit_code' in e && e.type === 'die') return `exit code ${e.exit_code ?? '?'}`
  if (e.type === 'health_status') return a.action?.split(':')[1]?.trim() ?? ''
  if (e.type === 'new_container' || e.type === 'container_removed') return a.name ?? ''
  if (e.type === 'disconnected') return a.error ?? ''
  return ''
}

export function EventTimeline({ events }: { events: (DockerEvent | HostEvent)[] }) {
  if (events.length === 0) return <p style={{ color: 'var(--fg-muted)' }}>Nenhum evento registrado.</p>
  return (
    <ol style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {events.map((e) => (
        <li
          key={e.id}
          style={{
            display: 'grid',
            gridTemplateColumns: '170px 140px 1fr',
            gap: 'var(--space-3)',
            padding: 'var(--space-2) 0',
            borderTop: '1px solid var(--border)',
            fontSize: 'var(--text-sm)',
          }}
        >
          <span style={{ color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>
            {new Date(e.occurred_at).toLocaleString('pt-BR')}
          </span>
          <span style={{ fontWeight: 600, color: critical.has(e.type) ? 'var(--error)' : 'inherit' }}>{labels[e.type] ?? e.type}</span>
          <span style={{ color: 'var(--fg-muted)', wordBreak: 'break-all' }}>{describe(e)}</span>
        </li>
      ))}
    </ol>
  )
}
