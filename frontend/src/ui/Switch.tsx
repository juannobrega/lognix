import * as RadixSwitch from '@radix-ui/react-switch'
import styles from './Switch.module.css'

interface Props {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  disabled?: boolean
  id?: string
  'aria-label'?: string
}

export function Switch({ checked, onCheckedChange, disabled, id, ...aria }: Props) {
  return (
    <RadixSwitch.Root
      className={styles.root}
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      id={id}
      aria-label={aria['aria-label']}
    >
      <RadixSwitch.Thumb className={styles.thumb} />
    </RadixSwitch.Root>
  )
}
