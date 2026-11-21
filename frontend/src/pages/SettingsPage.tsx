import { NavLink, Outlet } from 'react-router-dom'

const tabs = [
  { to: '/settings/users', label: 'Usuários' },
  { to: '/settings/ai', label: 'IA' },
  { to: '/settings/usage', label: 'Consumo' },
  { to: '/settings/system', label: 'Sistema' },
]

export function SettingsPage() {
  return (
    <>
      <h1>Configurações</h1>
      <nav aria-label="Configurações" style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-5)' }}>
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} style={({ isActive }) => ({ fontWeight: isActive ? 700 : 400 })}>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </>
  )
}
