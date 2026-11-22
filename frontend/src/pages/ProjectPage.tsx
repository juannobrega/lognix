import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { AnalysisRun, DockerEvent, Pattern, Project, TriggerFired } from '../api/types'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { TriggerList } from '../analysis/TriggerList'
import { ApiError } from '../api/client'
import { EventTimeline } from '../components/EventTimeline'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { ContainerStateBadge, HostStatusBadge } from '../components/StatusBadge'
import { LogViewer } from '../logs/LogViewer'
import { useProjectLogs, type Period } from '../logs/useProjectLogs'

export function ProjectPage() {
  const { id = '' } = useParams()
  const project = useQuery({ queryKey: ['project', id], queryFn: () => api<Project>(`/projects/${id}`), refetchInterval: 30_000 })
  const events = useQuery({ queryKey: ['project', id, 'events'], queryFn: () => api<DockerEvent[]>(`/projects/${id}/events`), refetchInterval: 30_000 })
  const [tab, setTab] = useState<'logs' | 'patterns' | 'triggers' | 'runs' | 'events' | 'env'>('logs')
  const qc = useQueryClient()
  const patterns = useQuery({ queryKey: ['project', id, 'patterns'], queryFn: () => api<Pattern[]>(`/projects/${id}/patterns`), enabled: tab === 'patterns', refetchInterval: 30_000 })
  const triggers = useQuery({ queryKey: ['project', id, 'triggers'], queryFn: () => api<TriggerFired[]>(`/projects/${id}/triggers`), refetchInterval: 30_000 })
  const runs = useQuery({ queryKey: ['project', id, 'runs'], queryFn: () => api<AnalysisRun[]>(`/projects/${id}/analysis-runs`), enabled: tab === 'runs', refetchInterval: 30_000 })
  const [analyzeMsg, setAnalyzeMsg] = useState<string | null>(null)
  const [minutes, setMinutes] = useState(15)
  const analyze = useMutation({
    mutationFn: () => api<{ triggers: TriggerFired[]; run: AnalysisRun }>(`/projects/${id}/analyze`, { method: 'POST', json: { minutes } }),
    onSuccess: (r) => {
      setAnalyzeMsg(`Analisadas ${r.run.lines_count} linhas, ${r.run.error_lines_count} de erro, ${r.run.new_patterns_count} padrões novos.`)
      void qc.invalidateQueries({ queryKey: ['project', id] })
      void qc.invalidateQueries({ queryKey: ['insights'] })
      setTab('triggers')
    },
    onError: (e) => setAnalyzeMsg(e instanceof ApiError ? `${e.message} ${e.action ?? ''}` : 'Falha na análise.'),
  })
  const togglePattern = useMutation({
    mutationFn: (p: Pattern) => api(`/projects/${id}/patterns/${p.id}/ignore`, { method: 'PUT', json: { ignored: !p.ignored } }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['project', id, 'patterns'] }),
  })
  const [live, setLive] = useState(true)
  const [follow, setFollow] = useState(true)
  const [period, setPeriod] = useState<Period>('15m')
  const [text, setText] = useState('')
  const [draft, setDraft] = useState('')
  const logs = useProjectLogs(id, { live, period, text })
  const p = project.data
  if (!p) return <p>Carregando…</p>

  const since = logs.monitoredSince ? new Date(logs.monitoredSince).toLocaleString('pt-BR') : null
  const empty =
    logs.loading ? (
      'Consultando…'
    ) : logs.error ? (
      `Erro: ${logs.error.message}`
    ) : p.host_status !== 'connected' ? (
      'Host desconectado. Os logs voltam quando o túnel for restabelecido.'
    ) : (
      <div>
        <span className="pulse" />
        Monitorando desde {since ?? 'agora'}. Aguardando as primeiras linhas.
        <br />
        <small>Linhas anteriores à marcação não são coletadas.</small>
      </div>
    )

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="row">
            {p.name} <ContainerStateBadge state={p.state} />
          </h1>
          <p className="subtitle">
            <Link to={`/hosts/${p.host_id}`}>{p.host_name}</Link> <HostStatusBadge status={p.host_status} />
            <span>· </span>
            <code>{p.image}</code>
            {p.image_digest && <span className="mono muted">{p.image_digest.replace('sha256:', '').slice(0, 12)}</span>}
            <span>· {p.kind === 'github' ? 'GitHub' : 'imagem Docker'}</span>
            {p.monitored_since && <span>· monitorado desde {new Date(p.monitored_since).toLocaleString('pt-BR')}</span>}
          </p>
        </div>
        <div className="row" style={{ flexWrap: 'nowrap' }}>
          <select value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} aria-label="Janela da análise manual">
            <option value={5}>últimos 5 min</option>
            <option value={15}>últimos 15 min</option>
            <option value={60}>última 1 h</option>
            <option value={360}>últimas 6 h</option>
          </select>
          <Button variant="primary" onClick={() => analyze.mutate()} loading={analyze.isPending}>
            Analisar agora
          </Button>
        </div>
      </div>
      {analyzeMsg && <Alert message={analyzeMsg} />}

      {p.state === 'removed' && <Alert kind="error" message="Este container desapareceu do host. Está em Containers excluídos; logs e eventos continuam acessíveis." />}
      <div role="tablist" className="tabs">
        {(['logs', 'triggers', 'patterns', 'runs', 'events', 'env'] as const).map((t) => (
          <button key={t} role="tab" className="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
            {{ logs: 'Logs', triggers: `Ocorrências (${triggers.data?.length ?? 0})`, patterns: 'Padrões', runs: 'Ciclos', events: `Eventos (${events.data?.length ?? 0})`, env: 'Ambiente' }[t]}
          </button>
        ))}
      </div>
      {tab === 'triggers' && <TriggerList triggers={triggers.data ?? []} />}
      {tab === 'patterns' && (
        <div className="card">
          <div className="card-header">
            <h2>Padrões</h2>
            <span className="muted" style={{ fontSize: 'var(--text-sm)' }}>
              Linhas agrupadas por template. Ignorar um padrão impede que ele abra issues (fase 1.3).
            </span>
          </div>
          {patterns.data?.length === 0 && <p className="muted card-body" style={{ margin: 0 }}>Nenhum padrão ainda. O primeiro ciclo roda até 30 s após a marcação.</p>}
          {patterns.data && patterns.data.length > 0 && (
            <table className="table">
              <thead>
                <tr>
                  <th>Nível</th>
                  <th>Template</th>
                  <th className="right">Ocorrências</th>
                  <th>Última vez</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {patterns.data.map((pt) => (
                  <tr key={pt.id} style={{ opacity: pt.ignored ? 0.5 : 1 }}>
                    <td>
                      <span style={{ fontWeight: 700, fontSize: 'var(--text-xs)', textTransform: 'uppercase', color: pt.level === 'error' ? 'var(--error)' : pt.level === 'warn' ? 'var(--warn)' : 'var(--fg-muted)' }}>
                        {pt.level}
                      </span>
                    </td>
                    <td className="mono" title={pt.sample} style={{ wordBreak: 'break-all' }}>
                      {pt.template}
                    </td>
                    <td className="right">{pt.count_total.toLocaleString('pt-BR')}</td>
                    <td className="muted">{new Date(pt.last_seen_at).toLocaleTimeString('pt-BR')}</td>
                    <td className="right">
                      <Button variant="ghost" size="sm" onClick={() => togglePattern.mutate(pt)}>
                        {pt.ignored ? 'Reativar' : 'Ignorar'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      {tab === 'runs' && (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Janela</th>
                <th className="right">Linhas</th>
                <th className="right">Erros</th>
                <th className="right">Avisos</th>
                <th className="right">Padrões novos</th>
                <th className="right">Duração</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {runs.data?.map((r) => (
                <tr key={r.id}>
                  <td className="muted">
                    {new Date(r.window_start).toLocaleTimeString('pt-BR')} → {new Date(r.window_end).toLocaleTimeString('pt-BR')}
                    {r.manual && ' · manual'}
                  </td>
                  <td className="right">{r.lines_count}</td>
                  <td className="right" style={{ color: r.error_lines_count ? 'var(--error)' : undefined }}>{r.error_lines_count}</td>
                  <td className="right">{r.warn_lines_count}</td>
                  <td className="right">{r.new_patterns_count}</td>
                  <td className="right muted">{r.duration_ms} ms</td>
                  <td style={{ color: r.status === 'failed' ? 'var(--error)' : 'var(--ok)' }}>{r.status === 'failed' ? `falhou: ${r.error ?? ''}` : r.status}</td>
                </tr>
              ))}
              {runs.data?.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted">Nenhum ciclo ainda.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {tab === 'events' && (
        <div className="card card-body">
          <EventTimeline events={events.data ?? []} />
        </div>
      )}
      {tab === 'env' && (
        <div className="card card-body">
          <p style={{ color: 'var(--fg-muted)', fontSize: 'var(--text-sm)' }}>
            Variáveis de ambiente do container, só por nome. Valores aparecem apenas para nomes seguros como APP_VERSION e NODE_ENV.
          </p>
          {!(p.env?.names as string[] | undefined)?.length && <p style={{ color: 'var(--fg-muted)' }}>Ainda não inspecionado.</p>}
          <ul style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }}>
            {((p.env?.names as string[] | undefined) ?? []).map((n) => (
              <li key={n}>
                {n}
                {(p.env?.safe as Record<string, string> | undefined)?.[n] !== undefined && <span style={{ color: 'var(--fg-muted)' }}> = {(p.env.safe as Record<string, string>)[n]}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div style={{ display: tab === 'logs' ? 'flex' : 'none', gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap', margin: 'var(--space-3) 0' }}>
        <div className="segmented" role="group" aria-label="Modo">
          <button onClick={() => setLive(true)} aria-pressed={live}>
            ● ao vivo
          </button>
          <button onClick={() => setLive(false)} aria-pressed={!live}>
            histórico
          </button>
        </div>
        <label className="muted">
          período{' '}
          <select value={period} onChange={(e) => setPeriod(e.target.value as Period)}>
            <option value="15m">últimos 15 min</option>
            <option value="1h">última 1 h</option>
            <option value="6h">últimas 6 h</option>
            <option value="24h">últimas 24 h</option>
            <option value="7d">últimos 7 dias</option>
          </select>
        </label>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            setText(draft.trim())
          }}
          style={{ display: 'flex', gap: 'var(--space-2)', flex: 1, minWidth: 240 }}
        >
          <input aria-label="Filtrar texto" placeholder="filtrar texto (contém)" value={draft} onChange={(e) => setDraft(e.target.value)} style={{ flex: 1 }} />
          <Button type="submit">Filtrar</Button>
        </form>
        {live && (
          <Button variant="ghost" onClick={() => setFollow((f) => !f)}>
            {follow ? '⏸ pausar' : '▶ seguir'}
          </Button>
        )}
        <span style={{ color: 'var(--fg-muted)', fontSize: 'var(--text-sm)' }}>{logs.lines.length} linhas</span>
      </div>

      {logs.truncated && <Alert message="Linhas antigas removidas da tela para manter o desempenho. Use o histórico para vê-las." />}
      {logs.hasMore && !logs.loading && (
        <div style={{ marginBottom: 'var(--space-2)' }}>
          <Button variant="ghost" onClick={logs.loadOlder}>
            ↑ carregar mais antigas
          </Button>
        </div>
      )}
      {tab === 'logs' && <LogViewer lines={logs.lines} follow={live && follow} onFollowChange={setFollow} empty={empty} onReachTop={logs.loadOlder} />}
    </>
  )
}
