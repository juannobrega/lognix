import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Host } from '../api/types'
import { Button } from '../components/Button'
import { EmptyState } from '../components/EmptyState'
import { HostStatusBadge } from '../components/StatusBadge'

export function HostsPage() {
  const hosts = useQuery({ queryKey: ['hosts'], queryFn: () => api<Host[]>('/hosts'), refetchInterval: 15_000 })
  return (
    <>
      <div className="page-header">
        <div>
          <h1>Hosts</h1>
          <p className="subtitle">Máquinas com Docker alcançadas por SSH. Nada é instalado nelas.</p>
        </div>
        <Link to="/hosts/new">
          <Button variant="primary">+ Cadastrar host</Button>
        </Link>
      </div>
      {hosts.data?.length === 0 && (
        <EmptyState title="Nenhum host cadastrado">
          <p>
            Cadastre uma máquina com Docker acessível por SSH. <Link to="/hosts/new">Cadastrar o primeiro host</Link>
          </p>
        </EmptyState>
      )}
      {hosts.data && hosts.data.length > 0 && (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Endereço</th>
                <th>Estado</th>
                <th>Docker</th>
                <th>Último erro</th>
              </tr>
            </thead>
            <tbody>
              {hosts.data.map((h) => (
                <tr key={h.id}>
                  <td>
                    <Link to={`/hosts/${h.id}`} style={{ fontWeight: 600 }}>
                      {h.name}
                    </Link>
                  </td>
                  <td className="mono">
                    {h.ssh_user}@{h.address}:{h.ssh_port}
                  </td>
                  <td>
                    <HostStatusBadge status={h.status} />
                  </td>
                  <td>{h.docker_version ?? '—'}</td>
                  <td className="muted" style={{ fontSize: 'var(--text-sm)' }}>
                    {h.last_error ?? ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
