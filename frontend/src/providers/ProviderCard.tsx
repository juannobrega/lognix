import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, api } from '../api/client'
import type { Provider } from '../api/types'
import { Button } from '../components/Button'
import { dateTime, usd } from '../components/format'
import { Badge } from '../components/StatusBadge'
import { useToast } from '../components/useToast'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { Switch } from '../ui/Switch'
import { Tooltip } from '../ui/Tooltip'
import { ProviderIcon } from './icons'
import { PROVIDER_TINT } from './kinds'
import { ProviderModels } from './ProviderModels'
import styles from './ProviderCard.module.css'

interface Props {
  provider: Provider
  /** Posição na cadeia de fallback, contando só os prontos. -1 quando o provedor não entra nela. */
  index: number
  /** Posição na lista inteira, que é o que as setas movem. */
  position: number
  total: number
  onEdit: () => void
  onMove: (direction: -1 | 1) => void
}

export function ProviderCard({ provider: p, index, position, total, onEdit, onMove }: Props) {
  const qc = useQueryClient()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['providers'] })
    void qc.invalidateQueries({ queryKey: ['summary'] })
  }

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api<Provider>(`/settings/ai/providers/${p.id}`, { method: 'PUT', json: { enabled } }),
    onSuccess: (r) => {
      toast.show(r.enabled ? `${r.name} ativado.` : `${r.name} desativado.`, 'success')
      invalidate()
    },
    onError: (e) => toast.show(e instanceof ApiError ? [e.message, e.action].filter(Boolean).join(' ') : 'Falha ao mudar o estado.', 'error'),
  })

  const test = useMutation({
    mutationFn: () => api<{ ok: boolean; model: string | null; latency_ms: number | null; cost_usd: string | null; error: string | null }>(
      `/settings/ai/providers/${p.id}/test`,
      { method: 'POST', json: {} },
    ),
    onSuccess: (r) => {
      toast.show(
        r.ok ? `${p.name} respondeu em ${((r.latency_ms ?? 0) / 1000).toFixed(1)}s, custo ${usd(r.cost_usd ?? 0)}.` : (r.error ?? 'O provedor recusou.'),
        r.ok ? 'success' : 'error',
      )
      invalidate()
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao testar.', 'error'),
  })

  const remove = useMutation({
    mutationFn: () => api(`/settings/ai/providers/${p.id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.show(`${p.name} removido.`, 'success')
      invalidate()
    },
  })

  const statusTone = p.paused_until ? 'warn' : p.last_status === 'ok' ? 'ok' : p.last_status === 'error' ? 'error' : 'neutral'
  const statusLabel = p.paused_until
    ? 'pausado por limite de uso'
    : p.last_status === 'ok'
      ? 'testado e funcionando'
      : p.last_status === 'error'
        ? 'último teste falhou'
        : 'nunca testado'

  return (
    <div className={styles.card}>
      <span className={styles.tile} style={{ ['--tint' as string]: PROVIDER_TINT[p.kind] }}>
        <ProviderIcon kind={p.kind} />
      </span>

      <div>
        <div className={styles.head}>
          <span className={styles.name}>{p.name}</span>
          <span className={styles.kind}>{p.label}</span>
          {p.ready && index >= 0 && (
            <Tooltip content={index === 0 ? 'Primeiro da cadeia: é quem recebe a chamada.' : `Entra se os ${index} anteriores falharem.`}>
              <span className={[styles.order, index === 0 ? styles.primary : ''].join(' ')}>
                {index === 0 ? 'principal' : `fallback ${index}`}
              </span>
            </Tooltip>
          )}
          <Badge tone={statusTone} label={statusLabel} />
        </div>
        <div className={styles.meta}>
          <span>modelo padrão: {p.default_model ? <code>{p.default_model}</code> : 'nenhum'}</span>
          <span>{p.models.length} modelo(s) cadastrado(s)</span>
          {p.has_credentials ? <span>credenciais salvas</span> : <span style={{ color: 'var(--warn)' }}>sem credenciais</span>}
          {p.last_checked_at && <span>testado em {dateTime(p.last_checked_at)}</span>}
        </div>
        {p.last_error && !p.ready && (
          <div className={styles.meta} style={{ color: 'var(--error)' }}>
            {p.last_error}
          </div>
        )}
      </div>

      <div className={styles.actions}>
        <div className={styles.arrows}>
          <button className={styles.arrow} onClick={() => onMove(-1)} disabled={position === 0} aria-label="Subir na cadeia de fallback">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
              <path d="m6 15 6-6 6 6" />
            </svg>
          </button>
          <button className={styles.arrow} onClick={() => onMove(1)} disabled={position === total - 1} aria-label="Descer na cadeia de fallback">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        </div>
        <Button size="sm" onClick={() => setOpen((v) => !v)}>
          {open ? 'Fechar' : 'Modelos'}
        </Button>
        <Button size="sm" onClick={() => test.mutate()} loading={test.isPending} disabled={!p.has_credentials || !p.default_model}>
          Testar
        </Button>
        <Button size="sm" onClick={onEdit}>
          Editar
        </Button>
        <Switch
          aria-label={`Ativar ${p.name}`}
          checked={p.enabled}
          disabled={!p.has_credentials || !p.default_model}
          onCheckedChange={(v) => toggle.mutate(v)}
        />
        <ConfirmDialog
          trigger={
            <Button variant="danger" size="sm">
              Remover
            </Button>
          }
          title={`Remover ${p.name}?`}
          description="O provedor sai da cadeia e seus modelos são apagados. As chamadas já registradas continuam no histórico de consumo."
          confirmLabel="Remover provedor"
          danger
          loading={remove.isPending}
          onConfirm={() => remove.mutate()}
        />
      </div>

      {open && (
        <div className={styles.models}>
          <ProviderModels provider={p} />
        </div>
      )}
    </div>
  )
}
