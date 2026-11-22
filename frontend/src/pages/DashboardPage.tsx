import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Health, Host, Project } from '../api/types'
import { EmptyState } from '../components/EmptyState'
import { HostStatusBadge } from '../components/StatusBadge'
import { useNotifications } from '../notifications/useNotifications'
import { NotificationItem } from './NotificationsPage'

export function DashboardPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => api<Health>('/health', { retry: false }) })
  const hosts = useQuery({ queryKey: ['hosts'], queryFn: () => api<Host[]>('/hosts'), refetchInterval: 15_000 })
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => api<Project[]>('/projects'), refetchInterval: 30_000 })
  const { list, seen } = useNotifications(false)

  if (hosts.data?.length === 0) {
    return (
      <>
        <div className="page-header">
          <div>
            <h1>Painel</h1>
          </div>
        </div>
        <EmptyState title="Nenhum host cadastrado ainda">
          <p>
            Cadastre o primeiro host para começar. <Link to="/hosts/new">Cadastrar host</Link>
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
            {hosts.data?.filter((h) => h.status === 'connected').length ?? 0} de {hosts.data?.length ?? 0} hosts conectados · {projects.data?.length ?? 0} projetos
            monitorados
            {health.data && <span>· backend v{health.data.version}</span>}
          </p>
        </div>
      </div>
      <div className="stack">
        <div className="grid-2">
          <section className="card">
            <div className="card-header">
              <h2>Hosts</h2>
              <Link to="/hosts">ver todos</Link>
            </div>
            <ul className="list">
              {hosts.data?.map((h) => (
                <li key={h.id} className="row" style={{ justifyContent: 'space-between' }}>
                  <Link to={`/hosts/${h.id}`} style={{ fontWeight: 500 }}>
                    {h.name}
                  </Link>
                  <HostStatusBadge status={h.status} />
                </li>
              ))}
            </ul>
          </section>
          <section className="card">
            <div className="card-header">
              <h2>Notificações {list.data && list.data.length > 0 && <span className="muted">({list.data.length})</span>}</h2>
              <Link to="/notifications">ver todas</Link>
            </div>
            {list.data?.length === 0 && (
              <p className="muted card-body" style={{ margin: 0 }}>
                Nada novo.
              </p>
            )}
            <ul className="list">{list.data?.slice(0, 5).map((n) => <NotificationItem key={n.id} n={n} onSeen={(id) => seen.mutate(id)} />)}</ul>
          </section>
        </div>
        <section>
          <h2 style={{ marginBottom: 'var(--space-3)' }}>Insights</h2>
          <EmptyState title="Insights chegam na fase 0.9.0">
            <p>Até lá, a coleta e o inventário já estão em andamento.</p>
          </EmptyState>
        </section>
      </div>
    </>
  )
}
