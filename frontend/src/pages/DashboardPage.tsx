import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Health } from '../api/types'
import { EmptyState } from '../components/EmptyState'

export function DashboardPage() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => api<Health>('/health', { retry: false }) })
  return (
    <>
      <h1>Painel</h1>
      <EmptyState title="Nenhum host cadastrado ainda">
        <p>
          Cadastre o primeiro host para começar a coletar logs. Disponível na fase 0.2.0.{' '}
          <Link to="/hosts">Ir para Hosts</Link>
        </p>
      </EmptyState>
      {health.data && (
        <p style={{ color: 'var(--fg-muted)', marginTop: 'var(--space-4)' }}>
          Backend v{health.data.version} · estado {health.data.status}
        </p>
      )}
    </>
  )
}
