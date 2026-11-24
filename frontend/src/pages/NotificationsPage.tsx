import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Notification } from '../api/types'
import { Button } from '../components/Button'
import { useToast } from '../components/useToast'
import { EmptyState } from '../components/EmptyState'
import { useNotifications } from '../notifications/useNotifications'

export function NotificationItem({ n, onSeen }: { n: Notification; onSeen?: (id: string) => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const monitor = useMutation({
    mutationFn: async () => {
      const current = await api<{ id: string; monitored: boolean }[]>(`/hosts/${n.host_id}/containers`)
      const ids = current.filter((c) => c.monitored).map((c) => c.id)
      await api(`/hosts/${n.host_id}/containers/monitored`, { method: 'PUT', json: { container_ids: [...ids, n.container_id] } })
      if (onSeen) onSeen(n.id)
    },
    onSuccess: () => {
      toast.show(`Monitorando ${String((n.payload as Record<string, string>).name ?? 'container')}.`, 'success')
      void qc.invalidateQueries({ queryKey: ['projects'] })
      void qc.invalidateQueries({ queryKey: ['host', n.host_id] })
      void qc.invalidateQueries({ queryKey: ['summary'] })
    },
    onError: () => toast.show('Não foi possível monitorar esse container.', 'error'),
  })
  const payload = n.payload as Record<string, string | undefined>
  return (
    <li style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-4)', alignItems: 'center' }}>
      <div>
        <div style={{ fontWeight: 600 }}>{n.title}</div>
        <div style={{ color: 'var(--fg-muted)', fontSize: 'var(--text-sm)' }}>
          {new Date(n.created_at).toLocaleString('pt-BR')}
          {payload.image && <> · {payload.image}</>}
          {payload.error && <> · {payload.error}</>}
          {n.host_id && (
            <>
              {' '}
              · <Link to={`/hosts/${n.host_id}`}>ver host</Link>
            </>
          )}
        </div>
      </div>
      {n.status === 'new' && (
        <div className="row" style={{ flexShrink: 0, flexWrap: 'nowrap' }}>
          {n.type === 'new_container' && n.container_id && (
            <Button variant="primary" size="sm" onClick={() => monitor.mutate()} loading={monitor.isPending}>
              Monitorar
            </Button>
          )}
          {n.type === 'host_disconnected' && n.host_id && (
            <Button
              size="sm"
              onClick={() => {
                void api(`/hosts/${n.host_id}/reconnect`, { method: 'POST' })
                  .then(() => toast.show('Reconexão iniciada.', 'info'))
                  .catch(() => toast.show('Falha ao pedir reconexão.', 'error'))
              }}
            >
              Reconectar
            </Button>
          )}
          {n.type === 'fingerprint_changed' && n.host_id && (
            <Link to={`/hosts/${n.host_id}`}>
              <Button variant="danger" size="sm">
                Revisar fingerprint
              </Button>
            </Link>
          )}
          {onSeen && (
            <Button variant="ghost" size="sm" onClick={() => onSeen(n.id)}>
              {n.type === 'new_container' ? 'Ignorar' : 'Visto'}
            </Button>
          )}
        </div>
      )}
    </li>
  )
}

export function NotificationsPage() {
  const [history, setHistory] = useState(false)
  const { list, seen, seenAll } = useNotifications(history)
  return (
    <>
      <div className="page-header">
        <div>
          <h1>Notificações</h1>
          <p className="subtitle">Ficam aqui até você marcar como vistas.</p>
        </div>
        <div className="row">
          <div className="segmented" role="group" aria-label="Filtro">
            <button onClick={() => setHistory(false)} aria-pressed={!history}>
              Novas
            </button>
            <button onClick={() => setHistory(true)} aria-pressed={history}>
              Histórico
            </button>
          </div>
          {!history && (list.data?.length ?? 0) > 0 && (
            <Button onClick={() => seenAll.mutate()} loading={seenAll.isPending}>
              Limpar todas
            </Button>
          )}
        </div>
      </div>
      {list.data?.length === 0 && <EmptyState title={history ? 'Nenhuma notificação vista' : 'Nenhuma notificação nova'} />}
      {list.data && list.data.length > 0 && (
        <div className="card">
          <ul className="list">
            {list.data.map((n) => (
              <NotificationItem key={n.id} n={n} onSeen={history ? undefined : (id) => seen.mutate(id)} />
            ))}
          </ul>
        </div>
      )}
    </>
  )
}
