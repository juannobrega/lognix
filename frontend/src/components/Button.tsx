import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import styles from './Button.module.css'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'md' | 'sm'
  loading?: boolean
  iconOnly?: boolean
  children?: ReactNode
}

/**
 * Encaminha a ref porque Radix monta gatilhos com `asChild`: Dialog e Tooltip precisam da
 * referência ao botão real para devolver o foco e posicionar o conteúdo.
 */
export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = 'secondary', size = 'md', loading, iconOnly, children, disabled, className, ...rest },
  ref,
) {
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
    <button ref={ref} className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? 'Aguarde…' : children}
    </button>
  )
})
