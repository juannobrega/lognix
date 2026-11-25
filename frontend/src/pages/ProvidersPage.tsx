import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { AiSettings, Provider } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { SkeletonRows } from '../components/Skeleton'
import { useToast } from '../components/useToast'
import { ProviderCard } from '../providers/ProviderCard'
import { ProviderDialog } from '../providers/ProviderDialog'

export function ProvidersPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const [dialog, setDialog] = useState<{ open: boolean; provider?: Provider }>({ open: false })
  const providers = useQuery({ queryKey: ['providers'], queryFn: () => api<Provider[]>('/settings/ai/providers') })
  const ai = useQuery({ queryKey: ['settings', 'ai'], queryFn: () => api<AiSettings>('/settings/ai') })

  const reorder = useMutation({
    mutationFn: (ids: string[]) => api<Provider[]>('/settings/ai/providers/reorder', { method: 'POST', json: { provider_ids: ids } }),
    onMutate: (ids) => {
      // Troca otimista: a seta precisa responder na hora, senão parece que não funcionou.
      const before = qc.getQueryData<Provider[]>(['providers'])
      if (before) {
        const byId = new Map(before.map((p) => [p.id, p]))
        qc.setQueryData<Provider[]>(['providers'], ids.map((id) => byId.get(id)).filter((p): p is Provider => !!p))
      }
      return { before }
    },
    onError: (e, _ids, ctx) => {
      if (ctx?.before) qc.setQueryData(['providers'], ctx.before)
      toast.show(e instanceof ApiError ? e.message : 'Falha ao reordenar.', 'error')
    },
    onSuccess: (list) => qc.setQueryData(['providers'], list),
  })

  if (providers.isError) return <ErrorState error={providers.error} onRetry={() => void providers.refetch()} />
  const list = providers.data
  if (!list) return <div className="card"><SkeletonRows rows={4} /></div>

  const ready = list.filter((p) => p.ready)
  const chain = list.map((p) => p.id)

  function move(id: string, direction: -1 | 1) {
    const from = chain.indexOf(id)
    const to = from + direction
    if (to < 0 || to >= chain.length) return
    const next = [...chain]
    ;[next[from], next[to]] = [next[to], next[from]]
    reorder.mutate(next)
  }

  return (
    <div className="stack" style={{ maxWidth: 1000 }}>
      <Alert
        kind="error"
        message="Trechos de log dos projetos monitorados são enviados ao provedor escolhido e ao fabricante do modelo."
        action="Não ative em projetos cujos logs contenham dados que não podem sair do seu ambiente. Nenhuma redação automática é feita nesta versão."
      />

      <section className="card">
        <div className="card-header">
          <div>
            <h2>Cadeia de fallback</h2>
            <p className="muted" style={{ margin: '2px 0 0', fontSize: 'var(--text-sm)' }}>
              {ready.length === 0
                ? 'Nenhum provedor pronto. Um provedor entra na cadeia quando tem credencial, modelo padrão e está ativado.'
                : ready.length === 1
                  ? `${ready[0].name} atende todas as chamadas. Sem um segundo provedor, uma queda dele deixa as ocorrências sem análise.`
                  : `${ready[0].name} atende; se recusar, a chamada desce a cadeia até ${ready[ready.length - 1].name}.`}
            </p>
          </div>
          <Button variant="primary" onClick={() => setDialog({ open: true })}>
            Novo provedor
          </Button>
        </div>

        {list.length === 0 ? (
          <EmptyState title="Nenhum provedor cadastrado">
            <p>
              A análise por IA precisa de pelo menos um. Dá para cadastrar OpenRouter, OpenAI ou Amazon Bedrock, e mais de um do mesmo tipo
              se você usa contas diferentes.
            </p>
            <Button variant="primary" onClick={() => setDialog({ open: true })}>
              Cadastrar o primeiro
            </Button>
          </EmptyState>
        ) : (
          list.map((p, i) => (
            <ProviderCard
              key={p.id}
              provider={p}
              index={ready.findIndex((r) => r.id === p.id)}
              position={i}
              total={list.length}
              onEdit={() => setDialog({ open: true, provider: p })}
              onMove={(d) => move(p.id, d)}
            />
          ))
        )}
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Como a cadeia é percorrida</h2>
        </div>
        <div className="card-body">
          <p className="muted" style={{ marginTop: 0 }}>
            A chamada vai ao primeiro provedor pronto. Erro de credencial, modelo inexistente, limite de uso ou indisponibilidade passam a
            vez ao seguinte, e o provedor que estourou limite fica pausado por alguns minutos. Resposta fora do formato esperado é retentada
            uma vez no mesmo provedor antes de descer a cadeia, porque trocar de modelo não costuma corrigir formato.
          </p>
          <p className="muted" style={{ marginBottom: 0 }}>
            Cada tentativa é registrada com provedor, modelo, tokens, custo e latência em <Link to="/settings/usage">Consumo</Link>. O
            interruptor geral da IA e os limites de tokens ficam em <Link to="/settings/ai">IA</Link>
            {ai.data && !ai.data.enabled ? ' — ele está desligado agora, então nada será chamado.' : '.'}
          </p>
        </div>
      </section>

      <ProviderDialog
        provider={dialog.provider}
        open={dialog.open}
        onOpenChange={(open) => setDialog((d) => ({ open, provider: open ? d.provider : undefined }))}
      />
    </div>
  )
}
