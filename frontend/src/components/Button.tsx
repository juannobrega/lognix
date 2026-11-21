import type { ButtonHTMLAttributes } from 'react'
import styles from './Button.module.css'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  loading?: boolean
}

export function Button({ variant = 'secondary', loading, children, disabled, className, ...rest }: Props) {
  const cls = [styles.button, variant !== 'secondary' ? styles[variant] : '', className ?? ''].join(' ')
  return (
    <button className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? 'Aguarde…' : children}
    </button>
  )
}
