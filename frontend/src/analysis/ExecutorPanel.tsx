import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ExecutorRunning } from '../api/types'
import { realtime } from '../realtime/socket'
import styles from './ExecutorPanel.module.css'

export function ExecutorPanel() {
  const [running, setRunning] = useState<ExecutorRunning[]>([])
  useEffect(
    () =>
      realtime.subscribe('executor', (msg) => {
        if (msg.type === 'executor') setRunning(msg.running as ExecutorRunning[])
      }),
    [],
  )
  if (running.length === 0) return null
  return (
    <aside className={styles.panel} aria-label="Executor">
      <div className={styles.head}>
        <span className="pulse" /> Executor · {running.length} em andamento
      </div>
      {running.map((r) => (
        <div key={`${r.container_id}-${r.trigger}`} className={styles.item}>
          <Link to={`/projects/${r.container_id}`} style={{ fontWeight: 500 }}>
            {r.container_name}
          </Link>
          <span className={styles.meta}>
            {r.host_name} · {r.trigger === 'manual' ? 'manual' : 'ciclo'} · {r.phase} · {(r.elapsed_ms / 1000).toFixed(1)}s
          </span>
        </div>
      ))}
    </aside>
  )
}
