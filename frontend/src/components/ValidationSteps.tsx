import type { ValidationStep } from '../api/types'
import styles from './ValidationSteps.module.css'

const icon: Record<ValidationStep['status'], string> = { ok: '✔', failed: '✘', running: '…', pending: '○' }

export function ValidationSteps({ steps }: { steps: ValidationStep[] }) {
  return (
    <ol className={styles.list} aria-label="Etapas de validação">
      {steps.map((s) => (
        <li key={s.number} className={styles.step}>
          <span className={[styles.icon, styles[s.status]].join(' ')} aria-label={s.status}>
            {icon[s.status]}
          </span>
          <div>
            <div>
              {s.number}. {s.name}
              {s.detail && <span className={styles.detail}> {s.detail}</span>}
            </div>
            {s.message && <div className={styles.message}>{s.message}</div>}
            {s.action && <div className={styles.action}>{s.action}</div>}
          </div>
        </li>
      ))}
    </ol>
  )
}
