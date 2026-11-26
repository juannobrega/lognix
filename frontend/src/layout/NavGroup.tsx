import { useEffect, useId, useState, type SVGProps } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import styles from './AppLayout.module.css'

export interface NavChild {
  to: string
  label: string
}

interface Props {
  to: string
  label: string
  icon: (p: SVGProps<SVGSVGElement>) => JSX.Element
  children: NavChild[]
  /** Badge opcional à direita do item pai. */
  badge?: JSX.Element
}

const STORAGE = 'lognix.nav.open'

function remembered(key: string): boolean | null {
  try {
    const raw = localStorage.getItem(STORAGE)
    const map = raw ? (JSON.parse(raw) as Record<string, boolean>) : {}
    return key in map ? map[key] : null
  } catch {
    return null // navegador sem storage: cai no comportamento automático
  }
}

function remember(key: string, open: boolean): void {
  try {
    const raw = localStorage.getItem(STORAGE)
    const map = raw ? (JSON.parse(raw) as Record<string, boolean>) : {}
    localStorage.setItem(STORAGE, JSON.stringify({ ...map, [key]: open }))
  } catch {
    // Sem storage a escolha vale só nesta sessão, que é melhor do que quebrar a navegação.
  }
}

/**
 * Item de menu que abre os próprios subitens.
 *
 * Duas coisas que o comportamento precisa acertar: estar dentro de uma subpágina **abre** o grupo
 * sozinho, senão o item ativo fica escondido; e clicar no pai navega, em vez de só abrir, porque
 * quem clica em "Configurações" quer ir para configurações.
 */
export function NavGroup({ to, label, icon: Icon, children, badge }: Props) {
  const { pathname } = useLocation()
  const inside = pathname === to || pathname.startsWith(`${to}/`)
  const [open, setOpen] = useState(() => remembered(to) ?? inside)
  const panelId = useId()

  // Navegar para dentro do grupo revela onde você está, mesmo que estivesse fechado.
  useEffect(() => {
    if (inside) setOpen(true)
  }, [inside])

  function toggle() {
    setOpen((v) => {
      remember(to, !v)
      return !v
    })
  }

  return (
    <div className={styles.group}>
      <div className={[styles.groupRow, inside && !open ? styles.rowInside : ''].join(' ')}>
        <NavLink
          to={to}
          className={({ isActive }) => [styles.link, styles.groupLink, isActive ? styles.active : ''].join(' ')}
        >
          <span className={styles.tile}>
            <Icon />
          </span>
          {label}
          {badge}
        </NavLink>
        <button
          type="button"
          className={styles.disclosure}
          aria-expanded={open}
          aria-controls={panelId}
          aria-label={`${open ? 'Recolher' : 'Expandir'} ${label}`}
          onClick={toggle}
        >
          <svg
            className={[styles.caret, open ? styles.caretOpen : ''].join(' ')}
            width="11"
            height="11"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            aria-hidden="true"
          >
            <path d="m9 6 6 6-6 6" />
          </svg>
        </button>
      </div>

      <div id={panelId} className={styles.children} hidden={!open}>
        {children.map((c) => (
          <NavLink
            key={c.to}
            to={c.to}
            className={({ isActive }) => [styles.child, isActive ? styles.childActive : ''].join(' ')}
          >
            {c.label}
          </NavLink>
        ))}
      </div>
    </div>
  )
}
