import type { ButtonHTMLAttributes } from 'react'
import styles from './Button.module.css'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'md' | 'sm'
  loading?: boolean
}

export function Button({ variant = 'secondary', size = 'md', loading, children, disabled, className, ...rest }: Props) {
  const cls = [styles.button, variant !== 'secondary' ? styles[variant] : '', size === 'sm' ? styles.sm : '', className ?? ''].join(' ')
  return (
    <button className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? 'Aguarde…' : children}
    </button>
  )
}
