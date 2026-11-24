import { NavLink, Outlet } from 'react-router-dom'
import { ExecutorPanel } from '../analysis/ExecutorPanel'
import { useAuth } from '../auth/useAuth'
import { Button } from '../components/Button'
import { useNotificationCount } from '../notifications/useNotifications'
import { Tooltip } from '../ui/Tooltip'
import { Icons } from './icons'
import { useTheme } from './useTheme'
import styles from './AppLayout.module.css'

const SECTIONS = [
  {
    label: 'Monitoramento',
    links: [
      { to: '/', label: 'Painel', end: true, icon: Icons.dashboard },
      { to: '/hosts', label: 'Hosts', icon: Icons.server },
      { to: '/projects', label: 'Projetos', icon: Icons.box },
    ],
  },
  {
    label: 'Análise',
    links: [
      { to: '/insights', label: 'Insights', icon: Icons.spark },
      { to: '/notifications', label: 'Notificações', icon: Icons.bell },
    ],
  },
  {
    label: 'Sistema',
    links: [{ to: '/settings', label: 'Configurações', icon: Icons.settings }],
  },
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

        <nav aria-label="Principal" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          {SECTIONS.map((section) => (
            <div key={section.label} className={styles.section}>
              <span className={styles.sectionLabel}>{section.label}</span>
              {section.links.map((l) => (
                <NavLink
                  key={l.to}
                  to={l.to}
                  end={l.end}
                  className={({ isActive }) => [styles.link, isActive ? styles.active : ''].join(' ')}
                >
                  <span className={styles.tile}>
                    <l.icon />
                  </span>
                  {l.label}
                  {l.to === '/notifications' && (count.data?.new ?? 0) > 0 && (
                    <span className={styles.count} aria-label={`${count.data?.new} novas`}>
                      {count.data?.new}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className={styles.footer}>
          <div className={styles.user}>
            <span className={styles.avatar} aria-hidden="true">
              {initials}
            </span>
            <span className={styles.userName}>{user?.name}</span>
          </div>
          <span className={styles.version}>v{__APP_VERSION__}</span>
          <div className={styles.footerRow}>
            <Tooltip content={theme === 'dark' ? 'Mudar para o tema claro' : 'Mudar para o tema escuro'}>
              <Button variant="ghost" size="sm" onClick={toggle} aria-label="Alternar tema">
                {theme === 'dark' ? <Icons.sun /> : <Icons.moon />}
                {theme === 'dark' ? 'Claro' : 'Escuro'}
              </Button>
            </Tooltip>
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
