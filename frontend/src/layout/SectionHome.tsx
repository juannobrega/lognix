import { useLocation } from 'react-router-dom'
import { SectionHub } from './SectionHub'
import { groupFor } from './navigation'

/**
 * Tela de entrada de qualquer grupo de navegação, descoberta pela rota.
 *
 * Não sabe nada sobre Configurações: lê o grupo dono do caminho atual e mostra os filhos dele.
 * Dar subpáginas a Hosts ou Projetos amanhã é acrescentar `children` em `navigation.ts` e apontar
 * a rota índice para cá.
 */
export function SectionHome() {
  const { pathname } = useLocation()
  const group = groupFor(pathname)
  return <SectionHub items={group?.children ?? []} />
}
