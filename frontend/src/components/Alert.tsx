import styles from './Alert.module.css'

export function Alert({ kind = 'info', message, action }: { kind?: 'info' | 'error'; message: string; action?: string }) {
  return (
    <div className={[styles.alert, kind === 'error' ? styles.error : ''].join(' ')} role={kind === 'error' ? 'alert' : 'status'}>
      {message}
      {action && <span className={styles.action}>{action}</span>}
    </div>
  )
}
