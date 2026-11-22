import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { Button } from '../components/Button'
import { useNotificationCount } from '../notifications/useNotifications'
import { ExecutorPanel } from '../analysis/ExecutorPanel'
import { Icons } from './icons'
import { useTheme } from './useTheme'
import styles from './AppLayout.module.css'

const links = [
  { to: '/', label: 'Painel', end: true, icon: Icons.dashboard },
  { to: '/hosts', label: 'Hosts', icon: Icons.server },
  { to: '/projects', label: 'Projetos', icon: Icons.box },
  { to: '/insights', label: 'Insights', icon: Icons.spark },
  { to: '/notifications', label: 'Notificações', icon: Icons.bell },
  { to: '/settings', label: 'Configurações', icon: Icons.settings },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const { theme, toggle } = useTheme()
  const count = useNotificationCount()
  const initials = (user?.name ?? '?')
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <img src="/logo.png" alt="Lognix" className={styles.logoImg} />
        </div>
        <nav className={styles.nav} aria-label="Principal">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => [styles.link, isActive ? styles.active : ''].join(' ')}>
              <l.icon className={styles.icon} />
              {l.label}
              {l.to === '/notifications' && (count.data?.new ?? 0) > 0 && (
                <span className={styles.count} aria-label={`${count.data?.new} novas`}>
                  {count.data?.new}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className={styles.footer}>
          <div className={styles.user}>
            <span className={styles.avatar} aria-hidden="true">
              {initials}
            </span>
            {user?.name}
          </div>
          <span>v{__APP_VERSION__} · IA desativada</span>
          <div className={styles.footerRow}>
            <Button variant="ghost" size="sm" onClick={toggle} aria-label="Alternar tema" title="Alternar tema">
              {theme === 'dark' ? <Icons.sun /> : <Icons.moon />}
              {theme === 'dark' ? 'Claro' : 'Escuro'}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => void logout()}>
              <Icons.logout /> Sair
            </Button>
          </div>
        </div>
      </aside>
      <main className={styles.main}>
        <Outlet />
      </main>
      <ExecutorPanel />
    </div>
  )
}
