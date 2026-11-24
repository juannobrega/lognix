import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { TriggerList } from '../analysis/TriggerList'
import { api } from '../api/client'
import type { Summary, TriggerFired } from '../api/types'
import { Alert } from '../components/Alert'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SkeletonRows } from '../components/Skeleton'

type Filter = 'all' | TriggerFired['type']
const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Todas' },
  { key: 'error', label: 'Erro' },
  { key: 'docker_event', label: 'Evento Docker' },
  { key: 'anomaly', label: 'Anomalia' },
  { key: 'manual', label: 'Manual' },
]

export function InsightsPage() {
  const [filter, setFilter] = useState<Filter>('all')
  const [text, setText] = useState('')
  const triggers = useQuery({
    queryKey: ['insights', 'unanalyzed'],
    queryFn: () => api<TriggerFired[]>('/insights/unanalyzed'),
    refetchInterval: 30_000,
  })
  const summary = useQuery({ queryKey: ['summary'], queryFn: () => api<Summary>('/summary') })

  const filtered = useMemo(() => {
    const list = triggers.data ?? []
    const needle = text.trim().toLowerCase()
    return list.filter(
      (t) =>
        (filter === 'all' || t.type === filter) &&
        (!needle ||
          (t.container_name ?? '').toLowerCase().includes(needle) ||
          (t.host_name ?? '').toLowerCase().includes(needle) ||
          (t.note ?? '').toLowerCase().includes(needle) ||
          t.sample_lines.some((l) => l.line.toLowerCase().includes(needle))),
    )
  }, [triggers.data, filter, text])

  const counts = useMemo(() => {
    const out: Record<string, number> = {}
    for (const t of triggers.data ?? []) out[t.type] = (out[t.type] ?? 0) + 1
    return out
  }, [triggers.data])

  if (triggers.isError) return <ErrorState error={triggers.error} onRetry={() => void triggers.refetch()} />

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Insights</h1>
          <p className="subtitle">Ocorrências detectadas pelo ciclo de análise.</p>
        </div>
      </div>

      {summary.data && !summary.data.ai_enabled && (
        <Alert
          message="A IA está desativada. As ocorrências abaixo foram detectadas pelas regras determinísticas, mas ninguém as explicou."
          action="Configure um provider em Configurações › IA. Ocorrências novas passarão a virar insights."
        />
      )}

      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
        <div className="segmented" role="group" aria-label="Filtrar por tipo">
          {FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)} aria-pressed={filter === f.key}>
              {f.label}
              {f.key !== 'all' && counts[f.key] ? ` (${counts[f.key]})` : ''}
            </button>
          ))}
        </div>
        <input
          aria-label="Buscar nas ocorrências"
          placeholder="buscar projeto, host ou texto"
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{ minWidth: 260 }}
        />
      </div>

      {triggers.isPending ? (
        <div className="card">
          <SkeletonRows rows={4} />
        </div>
      ) : filtered.length === 0 && (triggers.data?.length ?? 0) > 0 ? (
        <EmptyState title="Nenhuma ocorrência com esses filtros">
          <p>Ajuste o tipo ou a busca.</p>
        </EmptyState>
      ) : filtered.length === 0 ? (
        <EmptyState title="Nenhuma ocorrência registrada">
          <p>
            Tudo quieto nos projetos monitorados. <Link to="/projects">Ver projetos</Link>
          </p>
        </EmptyState>
      ) : (
        <TriggerList triggers={filtered} showProject />
      )}
    </>
  )
}
