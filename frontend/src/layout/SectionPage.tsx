import { Outlet, useLocation } from 'react-router-dom'
import { childFor, groupFor } from './navigation'

/**
 * Moldura de qualquer grupo de navegação: IA, Configurações, e o que vier depois.
 *
 * A navegação mora no sidebar e na tela de entrada; aqui o cabeçalho só diz onde a pessoa
 * chegou, lendo a mesma fonte que desenha as duas.
 */
export function SectionPage() {
  const { pathname } = useLocation()
  const group = groupFor(pathname)
  const child = childFor(pathname)

  return (
    <>
      <div className="page-header">
        <div>
          {child && <span className="eyebrow">{group?.label}</span>}
          <h1>{child?.label ?? group?.label}</h1>
          <p className="subtitle">{child?.description ?? group?.description}</p>
        </div>
      </div>
      <Outlet />
    </>
  )
}
