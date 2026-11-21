import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { Button } from '../components/Button'
import { useTheme } from './useTheme'
import styles from './AppLayout.module.css'

const links = [
  { to: '/', label: 'Painel', end: true },
  { to: '/hosts', label: 'Hosts' },
  { to: '/projects', label: 'Projetos' },
  { to: '/insights', label: 'Insights' },
  { to: '/notifications', label: 'Notificações' },
  { to: '/settings', label: 'Configurações' },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const { theme, toggle } = useTheme()
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>Lognix</div>
        <nav className={styles.nav} aria-label="Principal">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) => [styles.link, isActive ? styles.active : ''].join(' ')}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className={styles.footer}>
          <span>v{__APP_VERSION__} · IA desativada</span>
          <span>{user?.name}</span>
          <Button variant="ghost" onClick={toggle} aria-label="Alternar tema">
            Tema: {theme === 'dark' ? 'escuro' : 'claro'}
          </Button>
          <Button variant="ghost" onClick={() => void logout()}>
            Sair
          </Button>
        </div>
      </aside>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
