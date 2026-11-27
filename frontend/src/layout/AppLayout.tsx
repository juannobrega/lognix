import { NavLink, Outlet } from 'react-router-dom'
import { ExecutorPanel } from '../analysis/ExecutorPanel'
import { useAuth } from '../auth/useAuth'
import { Button } from '../components/Button'
import { useNotificationCount } from '../notifications/useNotifications'
import { Tooltip } from '../ui/Tooltip'
import { Icons } from './icons'
import { NavGroup } from './NavGroup'
import { SECTIONS } from './navigation'
import { useTheme } from './useTheme'
import styles from './AppLayout.module.css'

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
          <span role="img" aria-label="Lognix" className={styles.logoImg} />
        </div>

        <nav aria-label="Principal" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          {SECTIONS.map((section) => (
            <div key={section.label} className={styles.section}>
              <span className={styles.sectionLabel}>{section.label}</span>
              {section.links.map((l) =>
                'children' in l && l.children ? (
                  <NavGroup key={l.to} to={l.to} label={l.label} icon={l.icon}>
                    {l.children}
                  </NavGroup>
                ) : (
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
                ),
              )}
            </div>
          ))}
        </nav>

        <div className={styles.footer}>
          {/* O nome já estava aqui; agora leva a algum lugar — era o único jeito de alguém
              chegar à troca de senha. */}
          <NavLink
            to="/conta"
            className={({ isActive }) => [styles.user, isActive ? styles.userActive : ''].join(' ')}
          >
            <span className={styles.avatar} aria-hidden="true">
              {initials}
            </span>
            <span className={styles.userName}>{user?.name}</span>
          </NavLink>
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
