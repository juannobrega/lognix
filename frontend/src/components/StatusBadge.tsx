import type { HostStatus } from '../api/types'
import styles from './StatusBadge.module.css'

const map: Record<HostStatus, { label: string; tone: 'ok' | 'warn' | 'error' | 'neutral' }> = {
  connected: { label: 'conectado', tone: 'ok' },
  pending: { label: 'conectando', tone: 'warn' },
  disconnected: { label: 'desconectado', tone: 'warn' },
  error: { label: 'erro', tone: 'error' },
  removed: { label: 'removido', tone: 'neutral' },
}

export function HostStatusBadge({ status }: { status: HostStatus }) {
  const { label, tone } = map[status]
  return (
    <span className={[styles.badge, styles[tone]].join(' ')}>
      <span className={styles.dot} aria-hidden="true" />
      {label}
    </span>
  )
}

export function ContainerStateBadge({ state }: { state: string }) {
  const tone = state === 'running' ? 'ok' : state === 'restarting' ? 'warn' : state === 'exited' || state === 'dead' ? 'error' : 'neutral'
  return (
    <span className={[styles.badge, styles[tone]].join(' ')}>
      <span className={styles.dot} aria-hidden="true" />
      {state}
    </span>
  )
}
