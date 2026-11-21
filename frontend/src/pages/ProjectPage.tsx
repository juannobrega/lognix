import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Project } from '../api/types'
import { EmptyState } from '../components/EmptyState'
import { ContainerStateBadge, HostStatusBadge } from '../components/StatusBadge'

export function ProjectPage() {
  const { id = '' } = useParams()
  const project = useQuery({ queryKey: ['project', id], queryFn: () => api<Project>(`/projects/${id}`) })
  const p = project.data
  if (!p) return <p>Carregando…</p>
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
      <EmptyState title="Logs na interface chegam na fase 0.4.0">
        <p>Os logs deste projeto já estão sendo coletados pelo Alloy para o Loki desde a marcação.</p>
      </EmptyState>
    </>
  )
}
