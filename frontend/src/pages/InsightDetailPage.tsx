import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { InsightDetail } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { ErrorState } from '../components/ErrorState'
import { dateTime, timeOnly, tokens, usd } from '../components/format'
import { SkeletonRows } from '../components/Skeleton'
import { useToast } from '../components/useToast'
import { LOW_CONFIDENCE, SEVERITY_COLOR, SEVERITY_LABEL, TRIGGER_LABEL } from '../insights/severity'

const KIND_LABEL: Record<string, string> = { log_line: 'linha de log', docker_event: 'evento Docker', pattern: 'padrão' }

export function InsightDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const insight = useQuery({ queryKey: ['insight', id], queryFn: () => api<InsightDetail>(`/insights/${id}`) })

  const seen = useMutation({
    mutationFn: () => api(`/insights/${id}/seen`, { method: 'POST' }),
    onSuccess: () => {
      toast.show('Insight marcado como visto.', 'success')
      void qc.invalidateQueries({ queryKey: ['insights'] })
      void qc.invalidateQueries({ queryKey: ['insight', id] })
      void qc.invalidateQueries({ queryKey: ['summary'] })
      navigate('/insights')
    },
  })

  if (insight.isError) return <ErrorState error={insight.error} onRetry={() => void insight.refetch()} />
  const i = insight.data
  if (!i) return <div className="card"><SkeletonRows rows={6} /></div>

  const low = i.confidence < LOW_CONFIDENCE
  const call = i.calls.find((c) => c.status === 'ok') ?? i.calls[0]

  return (
    <div className="stack" style={{ maxWidth: 940 }}>
      <div className="page-header">
        <div>
          <div className="row" style={{ gap: 'var(--space-3)' }}>
            <span className="sev-pill" style={{ color: SEVERITY_COLOR[i.severity] }}>
              {SEVERITY_LABEL[i.severity]}
            </span>
            {i.container_name && (
              <Link to={`/projects/${i.container_id}`} style={{ fontWeight: 600 }}>
                {i.container_name}
              </Link>
            )}
            {i.host_name && <span className="muted">{i.host_name}</span>}
          </div>
          <h1 style={{ marginTop: 'var(--space-3)' }}>{i.title}</h1>
          <p className="subtitle">
            <span>{dateTime(i.created_at)}</span>
            {i.trigger_type && <span>· trigger {TRIGGER_LABEL[i.trigger_type]}</span>}
            {i.trigger_note && <span>· {i.trigger_note}</span>}
            {i.window_start && i.window_end && (
              <span>
                · janela {timeOnly(i.window_start)} → {timeOnly(i.window_end)}
              </span>
            )}
            <span style={{ color: low ? 'var(--warn)' : undefined, fontWeight: low ? 600 : 400 }}>
              · confiança {(i.confidence * 100).toFixed(0)}%
            </span>
          </p>
        </div>
        {i.status === 'new' && (
          <Button variant="primary" onClick={() => seen.mutate()} loading={seen.isPending}>
            Marcar como visto
          </Button>
        )}
      </div>

      {low && (
        <Alert
          message="A IA indicou baixa confiança nesta análise."
          action="Trate como hipótese e confira as evidências antes de agir."
        />
      )}
      {i.context_truncated && (
        <Alert message="O contexto foi cortado para caber no limite de tokens: parte das linhas não foi enviada ao provider." />
      )}

      <section className="card">
        <div className="card-body prose">
          <h2>O que aconteceu</h2>
          <p style={{ whiteSpace: 'pre-wrap' }}>{i.summary}</p>
          <div className="divider" />
          <h2>Causa provável</h2>
          <p style={{ whiteSpace: 'pre-wrap' }}>{i.probable_cause}</p>
          <div className="divider" />
          <h2>Ação sugerida</h2>
          <p style={{ whiteSpace: 'pre-wrap' }}>{i.suggested_action}</p>
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Evidências</h2>
          <span className="muted" style={{ fontSize: 'var(--text-sm)' }}>
            As linhas e eventos reais que a IA citou. Ela indica índices; o Lognix resolve.
          </span>
        </div>
        <ul className="list">
          {i.evidence.map((e, n) => (
            <li key={`${e.kind}-${e.index}-${n}`}>
              <div className="row" style={{ gap: 'var(--space-2)', marginBottom: 4 }}>
                <span className="muted" style={{ fontSize: 'var(--text-sm)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {KIND_LABEL[e.kind] ?? e.kind}
                </span>
                {e.at && <span className="muted mono">{e.at}</span>}
                {e.count !== undefined && <span className="muted">{e.count} ocorrências</span>}
                {e.new && <span style={{ color: 'var(--warn)', fontSize: 'var(--text-sm)', fontWeight: 600 }}>NOVO</span>}
              </div>
              <pre className="codeblock" style={{ color: e.kind === 'log_line' ? 'var(--log-error-fg)' : 'var(--log-fg)' }}>
                {e.text}
              </pre>
            </li>
          ))}
        </ul>
        <div className="card-body" style={{ paddingTop: 0 }}>
          <Link to={`/projects/${i.container_id}`}>Ver os logs do projeto</Link>
        </div>
      </section>

      {call && (
        <section className="card">
          <div className="card-header">
            <h2>Chamada de IA</h2>
            <span className="muted mono" style={{ fontSize: 'var(--text-sm)' }}>{call.model}</span>
          </div>
          <div className="card-body">
            <dl className="kv">
              <dt>Custo</dt>
              <dd>
                {usd(call.cost_usd)}{' '}
                <span className="muted">
                  ({call.cost_source === 'provider' ? 'informado pelo provider' : call.cost_source === 'estimated' ? 'estimado pela tabela de preços' : 'desconhecido'})
                </span>
              </dd>
              <dt>Tokens</dt>
              <dd>
                {tokens(call.input_tokens)} entrada · {tokens(call.output_tokens)} saída
              </dd>
              <dt>Latência</dt>
              <dd>{(call.latency_ms / 1000).toFixed(1)} s</dd>
              <dt>Prompt</dt>
              <dd className="mono">{call.prompt_version}</dd>
              {i.calls.length > 1 && (
                <>
                  <dt>Tentativas</dt>
                  <dd>
                    {i.calls.length} ({i.calls.filter((c) => c.schema_retry).length} retry de formato)
                  </dd>
                </>
              )}
            </dl>
          </div>
        </section>
      )}

      <section className="card">
        <div className="card-header">
          <h2>Contexto enviado ao provider</h2>
          <span className="muted" style={{ fontSize: 'var(--text-sm)' }}>Exatamente o que saiu do seu ambiente.</span>
        </div>
        <details>
          <summary style={{ cursor: 'pointer', padding: 'var(--space-3) var(--space-5)' }}>Ver contexto completo</summary>
          <pre
            style={{
              margin: 0,
              background: 'var(--log-bg)',
              color: 'var(--log-fg)',
              padding: 'var(--space-4)',
              borderBottomLeftRadius: 'var(--radius-well)',
              borderBottomRightRadius: 'var(--radius-well)',
              overflowX: 'auto',
              fontSize: 'var(--text-sm)',
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
            }}
          >
            {i.sent_context}
          </pre>
        </details>
      </section>
    </div>
  )
}
