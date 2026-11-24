import type { ReactNode } from 'react'
import styles from './EmptyState.module.css'

export function EmptyState({ title, icon, children }: { title: string; icon?: ReactNode; children?: ReactNode }) {
  return (
    <div className={styles.empty}>
      {icon && <span className={styles.icon}>{icon}</span>}
      <div className={styles.title}>{title}</div>
      {children}
    </div>
  )
}
