import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Project } from '../api/types'
import { EmptyState } from '../components/EmptyState'
import { ContainerStateBadge, HostStatusBadge } from '../components/StatusBadge'

export function ProjectsPage() {
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => api<Project[]>('/projects'), refetchInterval: 30_000 })
  return (
    <>
      <div className="page-header">
        <div>
          <h1>Projetos</h1>
          <p className="subtitle">Containers monitorados. Cada um é um projeto, com logs, eventos e, em breve, insights.</p>
        </div>
      </div>
      {projects.data?.length === 0 && (
        <EmptyState title="Nenhum container monitorado">
          <p>
            Abra um host e marque os containers que quer monitorar. <Link to="/hosts">Ir para Hosts</Link>
          </p>
        </EmptyState>
      )}
      {projects.data && projects.data.length > 0 && (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Projeto</th>
                <th>Host</th>
                <th>Imagem</th>
                <th>Estado</th>
                <th>Tipo</th>
                <th>Monitorado desde</th>
              </tr>
            </thead>
            <tbody>
              {projects.data.map((p) => (
                <tr key={p.id}>
                  <td>
                    <Link to={`/projects/${p.id}`} style={{ fontWeight: 600 }}>
                      {p.name}
                    </Link>
                  </td>
                  <td>
                    <span className="row" style={{ gap: 8 }}>
                      <Link to={`/hosts/${p.host_id}`}>{p.host_name}</Link> <HostStatusBadge status={p.host_status} />
                    </span>
                  </td>
                  <td className="mono">{p.image}</td>
                  <td>
                    <ContainerStateBadge state={p.state} />
                  </td>
                  <td className="muted">{p.kind === 'github' ? 'GitHub' : 'imagem Docker'}</td>
                  <td className="muted">{p.monitored_since ? new Date(p.monitored_since).toLocaleString('pt-BR') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
