import * as RadixSelect from '@radix-ui/react-select'
import type { ReactNode } from 'react'
import styles from './Select.module.css'

export interface SelectOption {
  value: string
  label: ReactNode
}

interface Props {
  value: string
  onValueChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  'aria-label'?: string
  id?: string
  disabled?: boolean
  minWidth?: number
}

/** Select acessível de verdade: teclado, leitor de tela e tema seguem o Radix. */
export function Select({ value, onValueChange, options, placeholder, disabled, id, minWidth, ...aria }: Props) {
  return (
    <RadixSelect.Root value={value} onValueChange={onValueChange} disabled={disabled}>
      <RadixSelect.Trigger className={styles.trigger} id={id} aria-label={aria['aria-label']} style={minWidth ? { minWidth } : undefined}>
        <RadixSelect.Value placeholder={placeholder} />
        <RadixSelect.Icon className={styles.chevron}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content className={styles.content} position="popper" sideOffset={4}>
          <RadixSelect.Viewport className={styles.viewport}>
            {options.map((o) => (
              <RadixSelect.Item key={o.value} value={o.value} className={styles.item}>
                <RadixSelect.ItemText>{o.label}</RadixSelect.ItemText>
                <RadixSelect.ItemIndicator className={styles.check}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                </RadixSelect.ItemIndicator>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  )
}
