import type { ButtonHTMLAttributes, ReactNode } from 'react'
import styles from './Button.module.css'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'md' | 'sm'
  loading?: boolean
  iconOnly?: boolean
  children?: ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading,
  iconOnly,
  children,
  disabled,
  className,
  ...rest
}: Props) {
  const cls = [
    styles.button,
    variant !== 'secondary' ? styles[variant] : '',
    size === 'sm' ? styles.sm : '',
    iconOnly ? styles.icon : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <button className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? 'Aguarde…' : children}
    </button>
  )
}
