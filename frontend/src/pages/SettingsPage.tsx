import { Outlet, useLocation } from 'react-router-dom'

/** Título por rota. A navegação mora no sidebar; aqui só dizemos onde a pessoa chegou. */
const TITLES: Record<string, { title: string; hint: string }> = {
  users: { title: 'Usuários', hint: 'Quem entra no Lognix e com qual acesso.' },
  ai: { title: 'IA', hint: 'O interruptor geral da análise e os limites por chamada.' },
  providers: { title: 'Provedores', hint: 'Quem atende as chamadas, em que ordem, e com quais modelos.' },
  usage: { title: 'Consumo', hint: 'Chamadas, tokens, custo e confiabilidade de cada provedor.' },
  system: { title: 'Sistema', hint: 'Versão, serviços, métricas e retenção.' },
}

export function SettingsPage() {
  const { pathname } = useLocation()
  const current = TITLES[pathname.split('/')[2] ?? ''] ?? { title: 'Configurações', hint: '' }

  return (
    <>
      <div className="page-header">
        <div>
          <span className="eyebrow">Configurações</span>
          <h1>{current.title}</h1>
          {current.hint && <p className="subtitle">{current.hint}</p>}
        </div>
      </div>
      <Outlet />
    </>
  )
}
