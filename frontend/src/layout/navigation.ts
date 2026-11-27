import type { SVGProps } from 'react'
import { Icons } from './icons'

export interface NavChild {
  to: string
  label: string
  /** Uma frase do que se resolve ali. Vira a legenda do card e o subtítulo da página. */
  description: string
  icon: (p: SVGProps<SVGSVGElement>) => JSX.Element
}

export interface NavItem {
  to: string
  label: string
  icon: (p: SVGProps<SVGSVGElement>) => JSX.Element
  end?: boolean
  /** Quando presente, o item abre no sidebar e ganha uma tela de entrada com cards. */
  children?: NavChild[]
}

export interface NavSection {
  label: string
  links: NavItem[]
}

/**
 * Fonte única da navegação.
 *
 * O sidebar, o cabeçalho das páginas e a tela de entrada de cada grupo leem daqui. Quando isso
 * estava escrito em três lugares, bastava acrescentar uma subpágina para que um dos três ficasse
 * para trás sem ninguém perceber.
 */
export const SECTIONS: NavSection[] = [
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
      { to: '/insights', label: 'Insights', icon: Icons.bulb },
      { to: '/notifications', label: 'Notificações', icon: Icons.bell },
    ],
  },
  {
    label: 'Sistema',
    links: [
      {
        to: '/settings',
        label: 'Configurações',
        icon: Icons.settings,
        children: [
          {
            to: '/settings/users',
            label: 'Usuários',
            description: 'Quem entra no Lognix, e como se cria ou remove acesso.',
            icon: Icons.users,
          },
          {
            to: '/settings/ai',
            label: 'IA',
            description: 'O interruptor geral da análise e os limites de cada chamada.',
            icon: Icons.spark,
          },
          {
            to: '/settings/providers',
            label: 'Provedores',
            description: 'Quem atende as chamadas, em que ordem, e com quais modelos.',
            icon: Icons.plug,
          },
          {
            to: '/settings/usage',
            label: 'Consumo',
            description: 'Chamadas, tokens, custo e confiabilidade de cada provedor.',
            icon: Icons.cost,
          },
          {
            to: '/settings/mcp',
            label: 'MCP',
            description: 'Chaves, permissões e ferramentas que a IA acessa pelo protocolo.',
            icon: Icons.key,
          },
          {
            to: '/settings/system',
            label: 'Sistema',
            description: 'Versão, serviços, métricas e retenção dos dados.',
            icon: Icons.cpu,
          },
        ],
      },
    ],
  },
]

/** Encontra o grupo dono de um caminho. Usado pelo cabeçalho e pela tela de entrada. */
export function groupFor(pathname: string): NavItem | undefined {
  return SECTIONS.flatMap((s) => s.links).find(
    (l) => l.children && (pathname === l.to || pathname.startsWith(`${l.to}/`)),
  )
}

export function childFor(pathname: string): NavChild | undefined {
  return groupFor(pathname)?.children?.find((c) => c.to === pathname)
}
