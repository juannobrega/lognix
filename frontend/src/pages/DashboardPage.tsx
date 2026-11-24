import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { TriggerList } from '../analysis/TriggerList'
import { api } from '../api/client'
import type { Insight, Summary, TriggerFired } from '../api/types'
import { InsightCard } from '../insights/InsightCard'
import { Alert } from '../components/Alert'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SkeletonRows } from '../components/Skeleton'
import { compact } from '../components/format'
import { Stat, StatGrid } from '../components/Stat'
import { HostStatusBadge } from '../components/StatusBadge'
import { useNotifications } from '../notifications/useNotifications'
import { NotificationItem } from './NotificationsPage'

export function DashboardPage() {
  const summary = useQuery({ queryKey: ['summary'], queryFn: () => api<Summary>('/summary'), refetchInterval: 20_000 })
  const insights = useQuery({
    queryKey: ['insights', 'new', 'recent'],
    queryFn: () => api<Insight[]>('/insights?limit=5'),
    refetchInterval: 30_000,
  })
  const triggers = useQuery({
    queryKey: ['insights', 'unanalyzed', 'recent'],
    queryFn: () => api<TriggerFired[]>('/insights/unanalyzed?limit=5'),
    refetchInterval: 30_000,
  })
  const { list, seen } = useNotifications(false)

  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
  const s = summary.data

  if (s && s.hosts_total === 0) {
    return (
      <>
        <div className="page-header">
          <div>
            <h1>Painel</h1>
            <p className="subtitle">Bem-vindo ao Lognix.</p>
          </div>
        </div>
        <EmptyState title="Nenhum host cadastrado ainda">
          <p>
            Cadastre uma máquina com Docker acessível por SSH. Nada é instalado nela.{' '}
            <Link to="/hosts/new">Cadastrar o primeiro host</Link>
          </p>
        </EmptyState>
      </>
    )
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Painel</h1>
          <p className="subtitle">
            {s ? (
              <>
                <span>
                  {s.hosts_connected} de {s.hosts_total} hosts conectados
                </span>
                <span>· {s.projects_total} projetos monitorados</span>
                <span>· IA {s.ai_enabled ? 'ativa' : 'desativada'}</span>
              </>
            ) : (
              'Carregando…'
            )}
          </p>
        </div>
      </div>

      <div className="stack">
        <section className="card">
          <div className="card-header">
            <h2>Últimas 24 horas</h2>
          </div>
          <div className="card-body">
            {!s ? (
              <SkeletonRows rows={2} />
            ) : (
              <StatGrid>
                <Stat value={compact(s.lines_24h)} label="Linhas analisadas" hint={`${s.cycles_24h} ciclos`} />
                <Stat
                  value={compact(s.errors_24h)}
                  label="Linhas de erro"
                  tone={s.errors_24h > 0 ? 'warn' : undefined}
                  hint={s.lines_24h ? `${((s.errors_24h / s.lines_24h) * 100).toFixed(1)}% do total` : '—'}
                />
                <Stat
                  value={s.triggers_new_24h}
                  label="Ocorrências"
                  tone={s.triggers_new_24h > 0 ? 'warn' : undefined}
                  hint={s.triggers_unanalyzed > 0 ? `${s.triggers_unanalyzed} sem análise` : 'todas analisadas'}
                />
                <Stat
                  value={s.projects_with_errors_1h}
                  label="Projetos com erro na última hora"
                  tone={s.projects_with_errors_1h > 0 ? 'error' : 'ok'}
                />
                <Stat
                  value={s.cycles_failed_24h}
                  label="Ciclos com falha"
                  tone={s.cycles_failed_24h > 0 ? 'error' : 'ok'}
                  hint={s.cycles_failed_24h > 0 ? 'veja Sistema' : 'nenhuma'}
                />
              </StatGrid>
            )}
          </div>
        </section>

        <div className="grid-2">
          <section className="card">
            <div className="card-header">
              <h2>Hosts</h2>
              <Link to="/hosts">ver todos</Link>
            </div>
            {!s ? (
              <SkeletonRows rows={3} />
            ) : (
              <ul className="list">
                {s.hosts.map((h) => (
                  <li key={h.id} className="row" style={{ justifyContent: 'space-between' }}>
                    <span>
                      <Link to={`/hosts/${h.id}`} style={{ fontWeight: 500 }}>
                        {h.name}
                      </Link>
                      <span className="muted" style={{ marginLeft: 8, fontSize: 'var(--text-sm)' }}>
                        {h.monitored} monitorado{h.monitored === 1 ? '' : 's'}
                      </span>
                    </span>
                    <HostStatusBadge status={h.status} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Notificações {list.data && list.data.length > 0 && <span className="muted">({list.data.length})</span>}</h2>
              <Link to="/notifications">ver todas</Link>
            </div>
            {list.isPending ? (
              <SkeletonRows rows={2} />
            ) : list.data?.length === 0 ? (
              <p className="muted card-body" style={{ margin: 0 }}>
                Nada novo.
              </p>
            ) : (
              <ul className="list">
                {list.data?.slice(0, 4).map((n) => (
                  <NotificationItem key={n.id} n={n} onSeen={(id) => seen.mutate(id)} />
                ))}
              </ul>
            )}
          </section>
        </div>

        {s && s.top_projects.length > 0 && (
          <section className="card">
            <div className="card-header">
              <h2>Projetos mais ativos</h2>
              <Link to="/projects">ver todos</Link>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>Projeto</th>
                  <th>Host</th>
                  <th className="right">Linhas 24 h</th>
                  <th className="right">Erros 24 h</th>
                  <th className="right">Ocorrências</th>
                </tr>
              </thead>
              <tbody>
                {s.top_projects.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <Link to={`/projects/${p.id}`} style={{ fontWeight: 500 }}>
                        {p.name}
                      </Link>
                    </td>
                    <td className="muted">{p.host_name}</td>
                    <td className="right">{compact(p.lines_24h)}</td>
                    <td className="right" style={{ color: p.errors_24h ? 'var(--error)' : undefined, fontWeight: p.errors_24h ? 600 : 400 }}>
                      {p.errors_24h}
                    </td>
                    <td className="right">{p.triggers_24h}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        <section>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 'var(--space-3)' }}>
            <h2>Insights recentes</h2>
            <Link to="/insights">ver todos</Link>
          </div>
          {s && !s.ai_enabled && (
            <Alert
              message="A IA está desativada: as ocorrências são detectadas, mas não explicadas."
              action="Configure um provider em Configurações › IA para gerar insights."
            />
          )}
          {insights.isPending ? (
            <SkeletonRows rows={3} />
          ) : (insights.data?.length ?? 0) > 0 ? (
            <div className="card">
              {insights.data?.map((i) => (
                <InsightCard key={i.id} insight={i} />
              ))}
            </div>
          ) : (triggers.data?.length ?? 0) > 0 ? (
            <>
              <p className="muted" style={{ marginTop: 0 }}>
                Nenhum insight novo. Estas ocorrências foram detectadas mas não analisadas:
              </p>
              <TriggerList triggers={triggers.data ?? []} showProject />
            </>
          ) : (
            <TriggerList triggers={[]} />
          )}
        </section>
      </div>
    </>
  )
}
