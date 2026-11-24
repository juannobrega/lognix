import * as Dialog from '@radix-ui/react-dialog'
import { useState, type ReactNode } from 'react'
import { Button } from '../components/Button'
import styles from './Dialog.module.css'

interface Props {
  trigger: ReactNode
  title: string
  description: ReactNode
  confirmLabel?: string
  danger?: boolean
  /** Quando dado, exige digitar este texto para liberar a confirmação. */
  confirmText?: string
  onConfirm: () => void
  loading?: boolean
}

/** Confirmação de ação destrutiva. Com `confirmText`, exige digitar o nome do alvo. */
export function ConfirmDialog({
  trigger,
  title,
  description,
  confirmLabel = 'Confirmar',
  danger,
  confirmText,
  onConfirm,
  loading,
}: Props) {
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const blocked = confirmText !== undefined && typed !== confirmText

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        if (!v) setTyped('')
      }}
    >
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.content}>
          <Dialog.Title className={styles.title}>{title}</Dialog.Title>
          <Dialog.Description asChild>
            <div className={styles.description}>{description}</div>
          </Dialog.Description>
          {confirmText !== undefined && (
            <div>
              <label htmlFor="confirm-text">
                Digite <code>{confirmText}</code> para confirmar
              </label>
              <input id="confirm-text" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
            </div>
          )}
          <div className={styles.actions}>
            <Dialog.Close asChild>
              <Button>Cancelar</Button>
            </Dialog.Close>
            <Button
              variant={danger ? 'danger' : 'primary'}
              disabled={blocked}
              loading={loading}
              onClick={() => {
                onConfirm()
                setOpen(false)
              }}
            >
              {confirmLabel}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
