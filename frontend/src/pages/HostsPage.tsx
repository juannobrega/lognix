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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Hosts</h1>
        <Link to="/hosts/new">
          <Button variant="primary">Cadastrar host</Button>
        </Link>
      </div>
      {hosts.data?.length === 0 && (
        <EmptyState title="Nenhum host cadastrado">
          <p>
            Cadastre uma máquina com Docker acessível por SSH. Nada é instalado nela.{' '}
            <Link to="/hosts/new">Cadastrar o primeiro host</Link>
          </p>
        </EmptyState>
      )}
      {hosts.data && hosts.data.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--fg-muted)' }}>
              <th>Nome</th>
              <th>Endereço</th>
              <th>Estado</th>
              <th>Docker</th>
              <th>Último erro</th>
            </tr>
          </thead>
          <tbody>
            {hosts.data.map((h) => (
              <tr key={h.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td>
                  <Link to={`/hosts/${h.id}`}>{h.name}</Link>
                </td>
                <td>
                  {h.ssh_user}@{h.address}:{h.ssh_port}
                </td>
                <td>
                  <HostStatusBadge status={h.status} />
                </td>
                <td>{h.docker_version ?? '—'}</td>
                <td style={{ color: 'var(--fg-muted)', fontSize: 'var(--text-sm)' }}>{h.last_error ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}
