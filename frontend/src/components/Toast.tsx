import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { ToastContext, type ToastKind } from './toastContext'
import styles from './Toast.module.css'

interface Item {
  id: number
  message: string
  kind: ToastKind
}

let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([])

  const remove = useCallback((id: number) => setItems((list) => list.filter((i) => i.id !== id)), [])

  const show = useCallback(
    (message: string, kind: ToastKind = 'info') => {
      const id = nextId++
      setItems((list) => [...list, { id, message, kind }])
      window.setTimeout(() => remove(id), kind === 'error' ? 9000 : 5000)
    },
    [remove],
  )

  const api = useMemo(() => ({ show }), [show])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className={styles.wrap} role="status" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className={[styles.toast, styles[i.kind]].join(' ')}>
            <span className={styles.dot} aria-hidden="true" />
            <span>{i.message}</span>
            <button className={styles.close} onClick={() => remove(i.id)} aria-label="Fechar aviso">
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
