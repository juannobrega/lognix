import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { AlloyConfig, Container, Host, HostEvent, MonitoredResult } from '../api/types'
import { EventTimeline } from '../components/EventTimeline'
import { ContainerPicker } from '../hosts/ContainerPicker'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { HostStatusBadge } from '../components/StatusBadge'
import { ValidationSteps } from '../components/ValidationSteps'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { useToast } from '../components/useToast'
import { useValidation } from '../hosts/useValidation'

export function HostDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const toast = useToast()
  const [validationId, setValidationId] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [tab, setTab] = useState<'containers' | 'excluded' | 'events' | 'connection' | 'alloy'>('containers')
  const host = useQuery({ queryKey: ['host', id], queryFn: () => api<Host>(`/hosts/${id}`), refetchInterval: 10_000 })
  const containers = useQuery({
    queryKey: ['host', id, 'containers'],
    queryFn: () => api<Container[]>(`/hosts/${id}/containers`),
    refetchInterval: 15_000,
    retry: false,
  })
  const alloy = useQuery({ queryKey: ['host', id, 'alloy'], queryFn: () => api<AlloyConfig>(`/hosts/${id}/alloy-config`) })
  const excluded = useQuery({ queryKey: ['host', id, 'excluded'], queryFn: () => api<Container[]>(`/hosts/${id}/containers/excluded`), refetchInterval: 30_000 })
  const events = useQuery({ queryKey: ['host', id, 'events'], queryFn: () => api<HostEvent[]>(`/hosts/${id}/events`), refetchInterval: 30_000 })
  const validation = useValidation(validationId)

  const onErr = (err: unknown) => {
    const e = err instanceof ApiError ? err : new ApiError(0, 'network', 'Falha de rede.')
    setError(e)
    toast.show(e.message, 'error')
  }
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['host', id] })
    void qc.invalidateQueries({ queryKey: ['hosts'] })
  }
  const [alloyMsg, setAlloyMsg] = useState<string | null>(null)
  const saveMonitored = useMutation({
    mutationFn: (ids: string[]) => api<MonitoredResult>(`/hosts/${id}/containers/monitored`, { method: 'PUT', json: { container_ids: ids } }),
    onSuccess: (r) => {
      const msg = r.alloy.reload_ok
        ? `Config do Alloy aplicada: ${r.alloy.containers_in_config} containers em ${r.alloy.hosts_in_config} hosts.`
        : `Falha ao recarregar o Alloy, config anterior restaurada: ${r.alloy.error ?? ''}`
      setAlloyMsg(msg)
      toast.show(msg, r.alloy.reload_ok ? 'success' : 'error')
      void qc.invalidateQueries({ queryKey: ['host', id, 'containers'] })
      void qc.invalidateQueries({ queryKey: ['host', id, 'alloy'] })
      void qc.invalidateQueries({ queryKey: ['projects'] })
      void qc.invalidateQueries({ queryKey: ['summary'] })
    },
    onError: onErr,
  })
  const reconnect = useMutation({
    mutationFn: () => api<{ validation_id: string }>(`/hosts/${id}/reconnect`, { method: 'POST' }),
    onSuccess: (d) => {
      setValidationId(d.validation_id)
      invalidate()
    },
    onError: onErr,
  })
  const acceptFp = useMutation({
    mutationFn: () => api<{ validation_id: string }>(`/hosts/${id}/accept-fingerprint`, { method: 'POST' }),
    onSuccess: (d) => {
      setValidationId(d.validation_id)
      invalidate()
    },
    onError: onErr,
  })
  const remove = useMutation({
    mutationFn: () => api(`/hosts/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      invalidate()
      navigate('/hosts')
    },
    onError: onErr,
  })

  const h = host.data
  if (!h) return <p>Carregando…</p>

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="row">
            {h.name} <HostStatusBadge status={h.status} />
          </h1>
          <p className="subtitle">
            <span className="mono">
              {h.ssh_user}@{h.address}:{h.ssh_port}
            </span>
            <span>· Docker {h.docker_version ?? '—'}</span>
            {h.tunnel?.connected_since && <span>· conectado desde {new Date(h.tunnel.connected_since).toLocaleString('pt-BR')}</span>}
          </p>
        </div>
        <div className="row">
          <Button onClick={() => reconnect.mutate()} loading={reconnect.isPending}>
            Reconectar
          </Button>
          <ConfirmDialog
            trigger={<Button variant="danger">Remover</Button>}
            title={`Remover o host ${h.name}?`}
            description={
              <>
                O túnel é encerrado e o host sai da lista. Containers, logs, padrões e insights continuam no histórico, e nada é alterado na
                máquina monitorada.
              </>
            }
            confirmLabel="Remover host"
            confirmText={h.name}
            danger
            loading={remove.isPending}
            onConfirm={() => remove.mutate()}
          />
        </div>
      </div>

      {error && <Alert kind="error" message={error.message} action={error.action} />}
      {h.last_error && h.status !== 'connected' && (
        <Alert
          kind="error"
          message={h.last_error}
          action={h.last_error.includes('chave do servidor mudou') ? 'Se a mudança for esperada, aceite o novo fingerprint abaixo.' : undefined}
        />
      )}
      {h.last_error?.includes('chave do servidor mudou') && (
        <Button variant="danger" onClick={() => acceptFp.mutate()} loading={acceptFp.isPending} style={{ marginBottom: 'var(--space-4)' }}>
          Aceitar novo fingerprint e reconectar
        </Button>
      )}

      {validation.data && validation.data.status !== 'ok' && (
        <section style={{ marginBottom: 'var(--space-5)' }}>
          <h2>Validação</h2>
          <ValidationSteps steps={validation.data.steps} />
        </section>
      )}

      <div role="tablist" className="tabs">
        {(['containers', 'excluded', 'events', 'connection', 'alloy'] as const).map((t) => (
          <button key={t} role="tab" className="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
            {{ containers: `Containers (${containers.data?.length ?? 0})`, excluded: `Excluídos (${excluded.data?.length ?? 0})`, events: 'Eventos', connection: 'Conexão', alloy: 'Config do Alloy' }[t]}
          </button>
        ))}
      </div>

      {tab === 'containers' && (
        <div className="card">
          {h.status !== 'connected' && (
            <p className="muted" style={{ padding: 'var(--space-3) var(--space-5)', margin: 0, borderBottom: '1px solid var(--divider)' }}>
              Host desconectado. Mostrando o último inventário conhecido.
            </p>
          )}
          {(containers.error || alloyMsg) && (
            <div style={{ padding: 'var(--space-4) var(--space-5) 0' }}>
              {containers.error && <Alert kind="error" message={(containers.error as ApiError).message} />}
              {alloyMsg && <Alert message={alloyMsg} />}
            </div>
          )}
          {containers.data && containers.data.length === 0 && (
            <p className="muted card-body" style={{ margin: 0 }}>
              Nenhum container neste host.
            </p>
          )}
          {containers.data && containers.data.length > 0 && (
            <ContainerPicker containers={containers.data} onSave={(ids) => saveMonitored.mutate(ids)} saving={saveMonitored.isPending} />
          )}
        </div>
      )}

      {tab === 'excluded' && (
        <div className="card">
          <div className="card-header">
            <h2>Containers excluídos</h2>
            <span className="muted" style={{ fontSize: 'var(--text-sm)' }}>
              Desapareceram do Docker. Insights e eventos continuam acessíveis.
            </span>
          </div>
          {excluded.data?.length === 0 && (
            <p className="muted card-body" style={{ margin: 0 }}>
              Nenhum.
            </p>
          )}
          {excluded.data && excluded.data.length > 0 && (
            <ul className="list">
              {excluded.data.map((c) => (
                <li key={c.id} className="row">
                  <Link to={`/projects/${c.id}`} style={{ fontWeight: 500 }}>
                    {c.name}
                  </Link>
                  <span className="mono muted">{c.image}</span>
                  <span className="muted" style={{ fontSize: 'var(--text-sm)', marginLeft: 'auto' }}>
                    visto pela última vez em {new Date(c.last_seen_at).toLocaleString('pt-BR')}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {tab === 'events' && (
        <div className="card card-body">
          <EventTimeline events={events.data ?? []} />
        </div>
      )}

      {tab === 'connection' && (
        <div className="card card-body">
          <dl className="kv">
            <dt>Autenticação</dt>
            <dd>{{ key: 'chave privada', key_passphrase: 'chave com passphrase', password: 'senha' }[h.ssh_auth_method]}</dd>
            <dt>Fingerprint</dt>
            <dd className="mono">{h.ssh_host_key_fingerprint ?? '—'}</dd>
            <dt>Socket do túnel</dt>
            <dd className="mono">{h.tunnel?.socket_path ?? '—'}</dd>
            <dt>Última verificação</dt>
            <dd>{h.tunnel?.last_check_at ? new Date(h.tunnel.last_check_at).toLocaleString('pt-BR') : '—'}</dd>
            <dt>Reconexões</dt>
            <dd>{h.tunnel?.reconnect_attempts ?? 0}</dd>
          </dl>
        </div>
      )}

      {tab === 'alloy' && alloy.data && (
        <div className="card">
          <div className="card-header">
            <h2>Config do Alloy</h2>
            <span className="muted mono">{alloy.data.path}</span>
          </div>
          <ul className="list">
            {alloy.data.versions.slice(0, 5).map((v) => (
              <li key={v.id} className="row" style={{ fontSize: 'var(--text-sm)' }}>
                <span className="mono muted">#{v.id}</span>
                <span className="muted">{new Date(v.applied_at).toLocaleString('pt-BR')}</span>
                <span>{v.reason}</span>
                <span style={{ marginLeft: 'auto', color: v.reload_ok ? 'var(--ok)' : 'var(--error)', fontWeight: 600 }}>
                  {v.reload_ok ? 'reload ok' : `falhou: ${v.error ?? ''}`}
                </span>
              </li>
            ))}
          </ul>
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
              lineHeight: 1.5,
            }}
          >
            {alloy.data.current}
          </pre>
        </div>
      )}
    </>
  )
}
