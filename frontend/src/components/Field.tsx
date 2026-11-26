import { useId, type InputHTMLAttributes, type ReactNode } from 'react'
import styles from './Field.module.css'

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  help?: ReactNode
  error?: string
}

export function Field({ label, help, error, id, className, ...rest }: Props) {
  const autoId = useId()
  const inputId = id ?? autoId
  const describedBy = error ? `${inputId}-error` : help ? `${inputId}-help` : undefined
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={inputId}>
        {label}
      </label>
      <input
        className={[styles.input, className ?? ''].join(' ')}
        id={inputId}
        aria-invalid={!!error}
        aria-describedby={describedBy}
        {...rest}
      />
      {error ? (
        <span className={styles.error} id={`${inputId}-error`} role="alert">
          {error}
        </span>
      ) : help ? (
        <span className={styles.help} id={`${inputId}-help`}>
          {help}
        </span>
      ) : null}
    </div>
  )
}
