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
      <h1>Projetos</h1>
      {projects.data?.length === 0 && (
        <EmptyState title="Nenhum container monitorado">
          <p>
            Abra um host e marque os containers que quer monitorar. <Link to="/hosts">Ir para Hosts</Link>
          </p>
        </EmptyState>
      )}
      {projects.data && projects.data.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--fg-muted)' }}>
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
              <tr key={p.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td>
                  <Link to={`/projects/${p.id}`}>{p.name}</Link>
                </td>
                <td>
                  <Link to={`/hosts/${p.host_id}`}>{p.host_name}</Link> <HostStatusBadge status={p.host_status} />
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }}>{p.image}</td>
                <td>
                  <ContainerStateBadge state={p.state} />
                </td>
                <td style={{ color: 'var(--fg-muted)' }}>{p.kind === 'github' ? 'GitHub' : 'imagem Docker'}</td>
                <td style={{ color: 'var(--fg-muted)' }}>{p.monitored_since ? new Date(p.monitored_since).toLocaleString('pt-BR') : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}
