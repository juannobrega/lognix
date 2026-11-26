import { Outlet, useLocation } from 'react-router-dom'
import { childFor, groupFor } from '../layout/navigation'

/**
 * Moldura das Configurações. A navegação mora no sidebar e na tela de entrada; aqui o cabeçalho
 * só diz onde a pessoa chegou, lendo a mesma fonte que desenha as duas.
 */
export function SettingsPage() {
  const { pathname } = useLocation()
  const group = groupFor(pathname)
  const child = childFor(pathname)

  return (
    <>
      <div className="page-header">
        <div>
          {child && <span className="eyebrow">{group?.label ?? 'Configurações'}</span>}
          <h1>{child?.label ?? group?.label ?? 'Configurações'}</h1>
          <p className="subtitle">
            {child?.description ?? 'Tudo que o Lognix guarda sobre si mesmo: acesso, IA, provedores e estado do sistema.'}
          </p>
        </div>
      </div>
      <Outlet />
    </>
  )
}
