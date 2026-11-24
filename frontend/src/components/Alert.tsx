import type { ReactNode } from 'react'
import styles from './Alert.module.css'

const ICONS = {
  info: <circle cx="12" cy="12" r="9" />,
  error: <path d="M12 9v4m0 4h.01M10.3 3.9 2.4 17.1A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.9L13.7 3.9a2 2 0 0 0-3.4 0z" />,
  warn: <path d="M12 9v4m0 4h.01M10.3 3.9 2.4 17.1A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.9L13.7 3.9a2 2 0 0 0-3.4 0z" />,
}

export function Alert({
  kind = 'info',
  message,
  action,
}: {
  kind?: 'info' | 'error' | 'warn'
  message: ReactNode
  action?: ReactNode
}) {
  return (
    <div
      className={[styles.alert, kind !== 'info' ? styles[kind] : ''].join(' ')}
      role={kind === 'info' ? 'status' : 'alert'}
    >
      <svg
        className={styles.icon}
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        aria-hidden="true"
      >
        {ICONS[kind]}
        {kind === 'info' && <path d="M12 8h.01M11 12h1v4h1" />}
      </svg>
      <span>
        {message}
        {action && <span className={styles.action}>{action}</span>}
      </span>
    </div>
  )
}
