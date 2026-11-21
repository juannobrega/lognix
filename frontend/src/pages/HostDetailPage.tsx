import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { ContainerSummary, Host } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { ContainerStateBadge, HostStatusBadge } from '../components/StatusBadge'
import { ValidationSteps } from '../components/ValidationSteps'
import { useValidation } from '../hosts/useValidation'

export function HostDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [validationId, setValidationId] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const host = useQuery({ queryKey: ['host', id], queryFn: () => api<Host>(`/hosts/${id}`), refetchInterval: 10_000 })
  const containers = useQuery({
    queryKey: ['host', id, 'containers'],
    queryFn: () => api<ContainerSummary[]>(`/hosts/${id}/containers`),
    enabled: host.data?.status === 'connected',
    refetchInterval: 15_000,
    retry: false,
  })
  const validation = useValidation(validationId)

  const onErr = (err: unknown) => setError(err instanceof ApiError ? err : new ApiError(0, 'network', 'Falha de rede.'))
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['host', id] })
    void qc.invalidateQueries({ queryKey: ['hosts'] })
  }
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <div>
          <h1 style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
            {h.name} <HostStatusBadge status={h.status} />
          </h1>
          <p style={{ color: 'var(--fg-muted)', margin: 0 }}>
            {h.ssh_user}@{h.address}:{h.ssh_port} · Docker {h.docker_version ?? '—'}
            {h.tunnel?.connected_since && ` · conectado desde ${new Date(h.tunnel.connected_since).toLocaleString('pt-BR')}`}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <Button onClick={() => reconnect.mutate()} loading={reconnect.isPending}>
            Reconectar
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              if (window.confirm(`Remover o host ${h.name}? Os dados ficam no histórico; nada é apagado no host.`)) remove.mutate()
            }}
            loading={remove.isPending}
          >
            Remover
          </Button>
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

      <section style={{ marginBottom: 'var(--space-5)' }}>
        <h2>Conexão</h2>
        <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '4px 16px', margin: 0 }}>
          <dt style={{ color: 'var(--fg-muted)' }}>Autenticação</dt>
          <dd style={{ margin: 0 }}>{{ key: 'chave', key_passphrase: 'chave com passphrase', password: 'senha' }[h.ssh_auth_method]}</dd>
          <dt style={{ color: 'var(--fg-muted)' }}>Fingerprint</dt>
          <dd style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }}>{h.ssh_host_key_fingerprint ?? '—'}</dd>
          <dt style={{ color: 'var(--fg-muted)' }}>Socket do túnel</dt>
          <dd style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }}>{h.tunnel?.socket_path ?? '—'}</dd>
          <dt style={{ color: 'var(--fg-muted)' }}>Reconexões</dt>
          <dd style={{ margin: 0 }}>{h.tunnel?.reconnect_attempts ?? 0}</dd>
        </dl>
      </section>

      <section>
        <h2>Containers</h2>
        {h.status !== 'connected' && <p style={{ color: 'var(--fg-muted)' }}>Host desconectado. O inventário aparece quando o túnel estiver ativo.</p>}
        {containers.error && <Alert kind="error" message={(containers.error as ApiError).message} />}
        {containers.data && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--fg-muted)' }}>
                <th>Nome</th>
                <th>Imagem</th>
                <th>Estado</th>
                <th>Compose</th>
                <th>Monitorar</th>
              </tr>
            </thead>
            <tbody>
              {containers.data.map((c) => (
                <tr key={c.docker_id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td>{c.name}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }}>{c.image}</td>
                  <td>
                    <ContainerStateBadge state={c.state} />
                  </td>
                  <td style={{ color: 'var(--fg-muted)' }}>{c.compose_project ? `${c.compose_project} / ${c.compose_service ?? ''}` : '—'}</td>
                  <td style={{ color: 'var(--fg-muted)', fontSize: 'var(--text-xs)' }}>fase 0.3.0</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
