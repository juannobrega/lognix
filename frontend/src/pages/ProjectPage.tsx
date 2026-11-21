import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Project } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { ContainerStateBadge, HostStatusBadge } from '../components/StatusBadge'
import { LogViewer } from '../logs/LogViewer'
import { useProjectLogs, type Period } from '../logs/useProjectLogs'

export function ProjectPage() {
  const { id = '' } = useParams()
  const project = useQuery({ queryKey: ['project', id], queryFn: () => api<Project>(`/projects/${id}`) })
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
      <h1 style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
        {p.name} <ContainerStateBadge state={p.state} />
      </h1>
      <p style={{ color: 'var(--fg-muted)' }}>
        <Link to={`/hosts/${p.host_id}`}>{p.host_name}</Link> <HostStatusBadge status={p.host_status} /> · <code>{p.image}</code>
        {p.image_digest && <> · {p.image_digest.replace('sha256:', '').slice(0, 12)}</>} · tipo {p.kind === 'github' ? 'GitHub' : 'imagem Docker'}
        {p.monitored_since && <> · monitorado desde {new Date(p.monitored_since).toLocaleString('pt-BR')}</>}
      </p>

      <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap', margin: 'var(--space-3) 0' }}>
        <Button variant={live ? 'primary' : 'secondary'} onClick={() => setLive(true)} aria-pressed={live}>
          ● ao vivo
        </Button>
        <Button variant={!live ? 'primary' : 'secondary'} onClick={() => setLive(false)} aria-pressed={!live}>
          histórico
        </Button>
        <label style={{ color: 'var(--fg-muted)' }}>
          período{' '}
          <select value={period} onChange={(e) => setPeriod(e.target.value as Period)} style={{ padding: '6px 8px' }}>
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
          <input
            aria-label="Filtrar texto"
            placeholder="filtrar texto (contém)"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            style={{ flex: 1, padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 4, background: 'var(--bg-elevated)' }}
          />
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
      <LogViewer lines={logs.lines} follow={live && follow} onFollowChange={setFollow} empty={empty} onReachTop={logs.loadOlder} />
    </>
  )
}
