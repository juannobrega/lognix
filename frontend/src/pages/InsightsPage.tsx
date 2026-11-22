import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { TriggerFired } from '../api/types'
import { TriggerList } from '../analysis/TriggerList'
import { Alert } from '../components/Alert'

export function InsightsPage() {
  const unanalyzed = useQuery({ queryKey: ['insights', 'unanalyzed'], queryFn: () => api<TriggerFired[]>('/insights/unanalyzed'), refetchInterval: 30_000 })
  return (
    <>
      <div className="page-header">
        <div>
          <h1>Insights</h1>
          <p className="subtitle">Ocorrências detectadas pelo ciclo de análise. A IA que as explica chega na fase 0.9.0.</p>
        </div>
      </div>
      <Alert message="IA desativada: as ocorrências abaixo foram detectadas, mas não analisadas. Quando a IA for configurada, novas ocorrências gerarão insights." />
      <h2 style={{ marginBottom: 'var(--space-3)' }}>Ocorrências sem análise {unanalyzed.data && <span className="muted">({unanalyzed.data.length})</span>}</h2>
      <TriggerList triggers={unanalyzed.data ?? []} showProject />
    </>
  )
}
