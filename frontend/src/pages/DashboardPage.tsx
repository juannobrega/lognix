import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { TriggerList } from '../analysis/TriggerList'
import { api } from '../api/client'
import type { Insight, Severity, Summary, TriggerFired } from '../api/types'
import { InsightCard } from '../insights/InsightCard'
import { Alert } from '../components/Alert'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SkeletonRows } from '../components/Skeleton'
import { compact, usd } from '../components/format'
import { Stat, StatGrid } from '../components/Stat'
import { AreaChart } from '../charts/AreaChart'
import { BarList } from '../charts/BarList'
import { SEVERITY_LABEL, TRIGGER_LABEL } from '../insights/severity'
import { HostStatusBadge } from '../components/StatusBadge'
import { useNotifications } from '../notifications/useNotifications'
import { NotificationItem } from './NotificationsPage'

/** Da mais grave para a menos: a ordem da lista é a ordem de quem precisa de atenção. */
const ORDEM_SEVERIDADE: Severity[] = ['critical', 'high', 'medium', 'low', 'info']

/** Só a hora: a data inteira em 24 marcas não cabe e não acrescenta. */
function hora(iso: string): string {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit' }) + 'h'
}

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
        <section className="card card-brand">
          <div className="card-header">
            <div>
              <h2>Volume e erros, últimas 24 horas</h2>
              <p className="muted" style={{ margin: '2px 0 0', fontSize: 'var(--text-sm)' }}>
                {s && s.lines_24h > 0
                  ? `${((s.errors_24h / Math.max(1, s.lines_24h)) * 100).toFixed(1)}% das linhas foram erro`
                  : 'Nenhuma linha analisada ainda.'}
              </p>
            </div>
            {s && s.cycles_24h > 0 && <span className="meta">{s.cycles_24h} ciclos</span>}
          </div>
          <div className="card-body">
            {!s ? (
              <SkeletonRows rows={3} />
            ) : (
              <>
                <AreaChart
                  aria-label="Linhas analisadas por hora, nas últimas 24 horas"
                  altura={120}
                  formata={compact}
                  rotulos={s.lines_by_hour.map((p) => hora(p.hour))}
                  series={[
                    { nome: 'linhas analisadas', cor: 'var(--accent)', valores: s.lines_by_hour.map((p) => p.lines) },
                  ]}
                />
                {/* A taxa em gráfico próprio, e não como segunda série do volume: com erro em
                    torno de 5% do total, a linha ficaria rente ao zero e esconderia exatamente
                    o pico que alguém abre o painel para ver. */}
                <div style={{ marginTop: 'var(--space-5)' }}>
                  <AreaChart
                    aria-label="Porcentagem de linhas de erro por hora, nas últimas 24 horas"
                    altura={64}
                    formata={(v) => `${v.toFixed(1)}%`}
                    rotulos={s.lines_by_hour.map((p) => hora(p.hour))}
                    series={[
                      {
                        nome: 'taxa de erro',
                        cor: 'var(--error)',
                        valores: s.lines_by_hour.map((p) => (p.lines ? (p.errors / p.lines) * 100 : 0)),
                      },
                    ]}
                  />
                </div>
              </>
            )}
          </div>
        </section>

        <div className="grid-3">
          <section className="card">
            <div className="card-header">
              <h2>Insights em aberto</h2>
              <Link to="/insights">ver todos</Link>
            </div>
            <div className="card-body">
              {!s ? (
                <SkeletonRows rows={2} />
              ) : (
                <BarList
                  vazio="Nenhum insight em aberto."
                  itens={ORDEM_SEVERIDADE.filter((sev) =>
                    s.insights_by_severity.some((f) => f.key === sev),
                  ).map((sev) => ({
                    rotulo: SEVERITY_LABEL[sev] ?? sev,
                    valor: s.insights_by_severity.find((f) => f.key === sev)?.count ?? 0,
                    cor: `var(--sev-${sev})`,
                  }))}
                />
              )}
            </div>
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Ocorrências por tipo</h2>
              <span className="meta">24 h</span>
            </div>
            <div className="card-body">
              {!s ? (
                <SkeletonRows rows={2} />
              ) : (
                <BarList
                  vazio="Nenhuma ocorrência nas últimas 24 horas."
                  itens={s.triggers_by_type.map((f) => ({
                    rotulo: TRIGGER_LABEL[f.key] ?? f.key,
                    valor: f.count,
                  }))}
                />
              )}
            </div>
          </section>

          <section className="card">
            <div className="card-header">
              <h2>Custo da IA</h2>
              <Link to="/ai/usage">consumo</Link>
            </div>
            <div className="card-body">
              {!s ? (
                <SkeletonRows rows={2} />
              ) : s.cost_by_day.length === 0 ? (
                <p className="muted" style={{ margin: 0, fontSize: 'var(--text-sm)' }}>
                  {s.ai_enabled ? 'Nenhuma chamada ainda.' : 'A IA está desligada.'}
                </p>
              ) : (
                <>
                  <AreaChart
                    aria-label="Custo da IA por dia, nos últimos sete dias"
                    altura={80}
                    formata={(v) => usd(v)}
                    rotulos={s.cost_by_day.map((p) => p.day.slice(5))}
                    series={[
                      {
                        nome: 'custo',
                        cor: 'var(--brand-violet)',
                        valores: s.cost_by_day.map((p) => Number(p.cost_usd)),
                      },
                    ]}
                  />
                  <p className="muted" style={{ margin: 'var(--space-3) 0 0', fontSize: 'var(--text-sm)' }}>
                    {usd(s.cost_by_day.reduce((a, p) => a + Number(p.cost_usd), 0))} em{' '}
                    {s.cost_by_day.reduce((a, p) => a + p.calls, 0)} chamadas
                  </p>
                </>
              )}
            </div>
          </section>
        </div>

        <section className="card">
          <div className="card-header">
            <h2>Estado agora</h2>
          </div>
          <div className="card-body">
            {!s ? (
              <SkeletonRows rows={2} />
            ) : (
              <StatGrid>
                <Stat
                  value={`${s.hosts_connected}/${s.hosts_total}`}
                  label="Hosts conectados"
                  tone={s.hosts_connected < s.hosts_total ? 'warn' : 'ok'}
                />
                <Stat
                  value={s.projects_with_errors_1h}
                  label="Projetos com erro na última hora"
                  tone={s.projects_with_errors_1h > 0 ? 'error' : 'ok'}
                />
                <Stat
                  value={s.triggers_unanalyzed}
                  label="Ocorrências sem análise"
                  tone={s.triggers_unanalyzed > 0 ? 'warn' : 'ok'}
                  hint={s.ai_enabled ? undefined : 'a IA está desligada'}
                />
                <Stat
                  value={s.cycles_failed_24h}
                  label="Ciclos com falha"
                  tone={s.cycles_failed_24h > 0 ? 'error' : 'ok'}
                  hint={s.cycles_failed_24h > 0 ? 'veja Sistema' : undefined}
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
