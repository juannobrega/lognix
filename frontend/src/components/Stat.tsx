import type { ReactNode } from 'react'
import styles from './Stat.module.css'

export function Stat({
  value,
  label,
  hint,
  tone,
}: {
  value: ReactNode
  label: string
  hint?: ReactNode
  tone?: 'ok' | 'warn' | 'error'
}) {
  return (
    <div className={[styles.stat, tone ? styles[tone] : ''].join(' ')}>
      <span className={styles.value}>{value}</span>
      <span className={styles.label}>{label}</span>
      {hint && <span className={styles.hint}>{hint}</span>}
    </div>
  )
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className={styles.grid}>{children}</div>
}
