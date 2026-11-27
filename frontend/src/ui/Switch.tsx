import * as RadixSwitch from '@radix-ui/react-switch'
import { useEffect, useState } from 'react'
import styles from './Switch.module.css'

interface Props {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  disabled?: boolean
  /**
   * A resposta do servidor ainda não chegou. O interruptor já se move no clique e volta
   * sozinho se a mutação falhar — passar `isPending` em `disabled` fazia o contrário: ele
   * apagava, ficava parado, e só pulava para o outro lado quando a resposta voltava.
   */
  pending?: boolean
  id?: string
  'aria-label'?: string
}

export function Switch({ checked, onCheckedChange, disabled, pending, id, ...aria }: Props) {
  const [otimista, setOtimista] = useState<boolean | null>(null)

  // O estado otimista sai de cena quando a verdade chega: ou `checked` mudou, ou a mutação
  // terminou. Se terminou sem mudar nada, foi erro — e o interruptor volta para onde estava.
  useEffect(() => {
    if (!pending) setOtimista(null)
  }, [pending, checked])

  return (
    <RadixSwitch.Root
      className={styles.root}
      checked={otimista ?? checked}
      onCheckedChange={(v) => {
        setOtimista(v)
        onCheckedChange(v)
      }}
      disabled={disabled}
      id={id}
      aria-label={aria['aria-label']}
    >
      <RadixSwitch.Thumb className={styles.thumb} />
    </RadixSwitch.Root>
  )
}
