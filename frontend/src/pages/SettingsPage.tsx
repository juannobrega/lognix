import { NavLink, Outlet } from 'react-router-dom'

const tabs = [
  { to: '/settings/users', label: 'Usuários' },
  { to: '/settings/ai', label: 'IA' },
  { to: '/settings/providers', label: 'Provedores' },
  { to: '/settings/usage', label: 'Consumo' },
  { to: '/settings/system', label: 'Sistema' },
]

export function SettingsPage() {
  return (
    <>
      <div className="page-header">
        <div>
          <h1>Configurações</h1>
        </div>
      </div>
      <nav aria-label="Configurações" className="tabs">
        {tabs.map((t) => (
          <NavLink key={t.to} to={t.to} className={({ isActive }) => ['tab', isActive ? 'active' : ''].join(' ')}>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </>
  )
}
