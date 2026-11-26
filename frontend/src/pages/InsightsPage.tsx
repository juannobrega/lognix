import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { TriggerList } from '../analysis/TriggerList'
import { api } from '../api/client'
import type { Insight, Severity, Summary, TriggerFired } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SkeletonRows } from '../components/Skeleton'
import { useToast } from '../components/useToast'
import { InsightCard } from '../insights/InsightCard'
import { SEVERITY_LABEL, SEVERITY_ORDER } from '../insights/severity'

type Tab = 'new' | 'history' | 'unanalyzed'

export function InsightsPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const [tab, setTab] = useState<Tab>('new')
  const [severity, setSeverity] = useState<Severity | 'all'>('all')
  const [text, setText] = useState('')

  const summary = useQuery({ queryKey: ['summary'], queryFn: () => api<Summary>('/summary') })
  const list = useQuery({
    queryKey: ['insights', tab],
    queryFn: () => api<Insight[]>(tab === 'history' ? '/insights/history' : '/insights'),
    enabled: tab !== 'unanalyzed',
    refetchInterval: tab === 'new' ? 30_000 : false,
  })
  const unanalyzed = useQuery({
    queryKey: ['insights', 'unanalyzed'],
    queryFn: () => api<TriggerFired[]>('/insights/unanalyzed'),
    refetchInterval: 30_000,
  })

  const seenAll = useMutation({
    mutationFn: () => api<{ marked: number }>('/insights/seen-all', { method: 'POST' }),
    onSuccess: (r) => {
      toast.show(`${r.marked} insight(s) marcados como vistos.`, 'success')
      void qc.invalidateQueries({ queryKey: ['insights'] })
      void qc.invalidateQueries({ queryKey: ['summary'] })
    },
  })

  const filtered = useMemo(() => {
    const needle = text.trim().toLowerCase()
    return (list.data ?? []).filter(
      (i) =>
        (severity === 'all' || i.severity === severity) &&
        (!needle ||
          i.title.toLowerCase().includes(needle) ||
          i.summary.toLowerCase().includes(needle) ||
          (i.container_name ?? '').toLowerCase().includes(needle) ||
          (i.host_name ?? '').toLowerCase().includes(needle)),
    )
  }, [list.data, severity, text])

  const counts = useMemo(() => {
    const out: Partial<Record<Severity, number>> = {}
    for (const i of list.data ?? []) out[i.severity] = (out[i.severity] ?? 0) + 1
    return out
  }, [list.data])

  if (list.isError) return <ErrorState error={list.error} onRetry={() => void list.refetch()} />

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Insights</h1>
          <p className="subtitle">
            O que a IA entendeu das ocorrências detectadas pelo ciclo de análise.
            {summary.data && !summary.data.ai_enabled && ' A IA está desativada.'}
          </p>
        </div>
        {tab === 'new' && (list.data?.length ?? 0) > 0 && (
          <Button onClick={() => seenAll.mutate()} loading={seenAll.isPending}>
            Limpar todos
          </Button>
        )}
      </div>

      {summary.data && !summary.data.ai_enabled && (
        <Alert
          message="A IA está desativada: as ocorrências são detectadas pelas regras determinísticas, mas ninguém as explica."
          action="Configure um provider em Configurações › IA. Ocorrências novas passarão a virar insights."
        />
      )}

      <div role="tablist" className="tabs">
        <button role="tab" className="tab" aria-selected={tab === 'new'} onClick={() => setTab('new')}>
          Novos {tab !== 'unanalyzed' && list.data && tab === 'new' ? `(${list.data.length})` : ''}
        </button>
        <button role="tab" className="tab" aria-selected={tab === 'history'} onClick={() => setTab('history')}>
          Histórico
        </button>
        <button role="tab" className="tab" aria-selected={tab === 'unanalyzed'} onClick={() => setTab('unanalyzed')}>
          Sem análise {unanalyzed.data?.length ? `(${unanalyzed.data.length})` : ''}
        </button>
      </div>

      {tab === 'unanalyzed' ? (
        <>
          <p className="muted" style={{ marginTop: 0 }}>
            Ocorrências que o ciclo detectou mas ninguém explicou: a IA estava desligada, falhou, ou o projeto foi analisado antes de ela ser
            configurada.
          </p>
          {unanalyzed.isPending ? (
            <div className="card">
              <SkeletonRows rows={3} />
            </div>
          ) : (
            <TriggerList triggers={unanalyzed.data ?? []} showProject />
          )}
        </>
      ) : (
        <>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
            <div className="segmented" role="group" aria-label="Filtrar por severidade">
              <button onClick={() => setSeverity('all')} aria-pressed={severity === 'all'}>
                Todas
              </button>
              {SEVERITY_ORDER.map((s) => (
                <button key={s} onClick={() => setSeverity(s)} aria-pressed={severity === s}>
                  {SEVERITY_LABEL[s]}
                  {counts[s] ? ` (${counts[s]})` : ''}
                </button>
              ))}
            </div>
            <input
              aria-label="Buscar nos insights"
              placeholder="buscar título, projeto ou host"
              value={text}
              onChange={(e) => setText(e.target.value)}
              style={{ minWidth: 240 }}
            />
          </div>

          {list.isPending ? (
            <div className="card">
              <SkeletonRows rows={4} />
            </div>
          ) : filtered.length === 0 && (list.data?.length ?? 0) > 0 ? (
            <EmptyState title="Nenhum insight com esses filtros" />
          ) : filtered.length === 0 ? (
            <EmptyState title={tab === 'history' ? 'Nenhum insight visto ainda' : 'Nenhum insight novo'}>
              <p>
                {summary.data?.ai_enabled
                  ? 'Tudo quieto nos projetos monitorados.'
                  : 'Ative a IA para que as ocorrências virem insights.'}{' '}
                <Link to="/projects">Ver projetos</Link>
              </p>
            </EmptyState>
          ) : (
            <div className="card">
              {filtered.map((i) => (
                <InsightCard key={i.id} insight={i} />
              ))}
            </div>
          )}
        </>
      )}
    </>
  )
}
