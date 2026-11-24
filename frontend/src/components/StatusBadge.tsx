import type { ContainerState, HostStatus } from '../api/types'
import styles from './StatusBadge.module.css'

type Tone = 'ok' | 'warn' | 'error' | 'neutral'

function Badge({ tone, label, pulsing }: { tone: Tone; label: string; pulsing?: boolean }) {
  return (
    <span className={[styles.badge, styles[tone], pulsing ? styles.pulsing : ''].join(' ')}>
      <span className={styles.dot} aria-hidden="true" />
      <span className={styles.label}>{label}</span>
    </span>
  )
}

const HOST: Record<HostStatus, { label: string; tone: Tone; pulsing?: boolean }> = {
  connected: { label: 'conectado', tone: 'ok' },
  pending: { label: 'conectando', tone: 'warn', pulsing: true },
  disconnected: { label: 'desconectado', tone: 'warn' },
  error: { label: 'erro', tone: 'error' },
  removed: { label: 'removido', tone: 'neutral' },
}

export function HostStatusBadge({ status }: { status: HostStatus }) {
  const s = HOST[status]
  return <Badge tone={s.tone} label={s.label} pulsing={s.pulsing} />
}

const CONTAINER: Record<string, { label: string; tone: Tone }> = {
  running: { label: 'rodando', tone: 'ok' },
  restarting: { label: 'reiniciando', tone: 'warn' },
  paused: { label: 'pausado', tone: 'warn' },
  exited: { label: 'parado', tone: 'neutral' },
  dead: { label: 'morto', tone: 'error' },
  created: { label: 'criado', tone: 'neutral' },
  removed: { label: 'removido', tone: 'neutral' },
}

export function ContainerStateBadge({ state }: { state: ContainerState | string }) {
  const s = CONTAINER[state] ?? { label: state, tone: 'neutral' as Tone }
  return <Badge tone={s.tone} label={s.label} />
}

export { Badge }
