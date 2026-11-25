import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Fragment, type ReactNode } from 'react'
import styles from './Menu.module.css'

export interface MenuAction {
  label: string
  onSelect: () => void
  danger?: boolean
  disabled?: boolean
  /** Explica por que o item está desabilitado; vira o `title` da linha. */
  hint?: string
  separatorBefore?: boolean
}

/**
 * Ações de uma linha de tabela, atrás de um botão só.
 *
 * Numa tabela densa, cinco botões por linha competem com o dado. Aqui fica a ação que o usuário
 * procura quando já decidiu agir sobre aquela linha — o que ele consulta de relance fica em coluna.
 */
export function Menu({ actions, label, children }: { actions: MenuAction[]; label: string; children?: ReactNode }) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger className={styles.trigger} aria-label={label}>
        {children ?? (
          <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <circle cx="12" cy="5" r="1.7" />
            <circle cx="12" cy="12" r="1.7" />
            <circle cx="12" cy="19" r="1.7" />
          </svg>
        )}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className={styles.content} align="end" sideOffset={4}>
          {actions.map((a) => (
            <Fragment key={a.label}>
              {a.separatorBefore && <DropdownMenu.Separator className={styles.separator} />}
              <DropdownMenu.Item
                className={[styles.item, a.danger ? styles.danger : ''].join(' ')}
                disabled={a.disabled}
                title={a.disabled ? a.hint : undefined}
                onSelect={a.onSelect}
              >
                {a.label}
              </DropdownMenu.Item>
            </Fragment>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
