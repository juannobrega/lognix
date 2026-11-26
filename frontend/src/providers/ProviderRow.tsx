import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, api } from '../api/client'
import type { Provider } from '../api/types'
import { dateTime, usd } from '../components/format'
import { Badge } from '../components/StatusBadge'
import { useToast } from '../components/useToast'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { Menu } from '../ui/Menu'
import { Switch } from '../ui/Switch'
import { Tooltip } from '../ui/Tooltip'
import { ProviderIcon } from './icons'
import { PROVIDER_TINT } from './kinds'
import { ProviderModels } from './ProviderModels'
import styles from './ProviderRow.module.css'

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

export function ProviderRow({ provider: p, index, position, total, onEdit, onMove }: Props) {
  const qc = useQueryClient()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['providers'] })
    void qc.invalidateQueries({ queryKey: ['settings', 'ai'] })
    void qc.invalidateQueries({ queryKey: ['summary'] })
  }

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api<Provider>(`/settings/ai/providers/${p.id}`, { method: 'PUT', json: { enabled } }),
    onSuccess: (r) => {
      toast.show(r.enabled ? `${r.name} entrou na cadeia.` : `${r.name} saiu da cadeia.`, 'success')
      invalidate()
    },
    onError: (e) => toast.show(e instanceof ApiError ? [e.message, e.action].filter(Boolean).join(' ') : 'Falha ao mudar o estado.', 'error'),
  })

  const test = useMutation({
    mutationFn: () =>
      api<{ ok: boolean; latency_ms: number | null; cost_usd: string | null; error: string | null }>(
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

  const blocked = !p.has_credentials ? 'Faltam as credenciais.' : !p.default_model ? 'Falta o modelo padrão.' : undefined

  const status = p.paused_until
    ? { tone: 'warn' as const, label: 'pausado', title: `Pausado por limite de uso até ${dateTime(p.paused_until)}.` }
    : p.last_status === 'ok'
      ? { tone: 'ok' as const, label: 'ok', title: p.last_checked_at ? `Último teste em ${dateTime(p.last_checked_at)}.` : 'Testado.' }
      : p.last_status === 'error'
        ? { tone: 'error' as const, label: 'falhou', title: p.last_error ?? 'O último teste falhou.' }
        : { tone: 'neutral' as const, label: 'nunca testado', title: 'Nenhum teste feito até agora.' }

  return (
    <>
      <tr>
        <td className={styles.order}>
          <span className={styles.arrows}>
            <button className={styles.arrow} onClick={() => onMove(-1)} disabled={position === 0} aria-label={`Subir ${p.name} na cadeia`}>
              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2">
                <path d="m6 15 6-6 6 6" />
              </svg>
            </button>
            <button
              className={styles.arrow}
              onClick={() => onMove(1)}
              disabled={position === total - 1}
              aria-label={`Descer ${p.name} na cadeia`}
            >
              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2">
                <path d="m6 9 6 6 6-6" />
              </svg>
            </button>
          </span>
          {index === 0 ? (
            <Tooltip content="Primeiro da cadeia: é quem recebe a chamada.">
              <span className={[styles.position, styles.primary].join(' ')}>1º</span>
            </Tooltip>
          ) : index > 0 ? (
            <Tooltip content={`Entra se os ${index} anteriores falharem.`}>
              <span className={styles.position}>{index + 1}º</span>
            </Tooltip>
          ) : (
            <Tooltip content={blocked ?? 'Desativado: fora da cadeia.'}>
              <span className={[styles.position, styles.out].join(' ')}>—</span>
            </Tooltip>
          )}
        </td>

        <td>
          <span className={styles.name}>
            <button
              className={styles.expand}
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              aria-label={`${open ? 'Esconder' : 'Ver'} os modelos de ${p.name}`}
            >
              <svg
                className={[styles.chevron, open ? styles.chevronOpen : ''].join(' ')}
                width="11"
                height="11"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
              >
                <path d="m9 6 6 6-6 6" />
              </svg>
            </button>
            <span className={styles.tile} style={{ ['--tint' as string]: PROVIDER_TINT[p.kind] }}>
              <ProviderIcon kind={p.kind} width={17} height={17} />
            </span>
            <span>
              <span className={styles.title}>{p.name}</span>
              <div className={styles.kind}>{p.label}</div>
            </span>
          </span>
        </td>

        <td>
          {p.default_model ? (
            <span className="mono">{p.default_model}</span>
          ) : (
            <span style={{ color: 'var(--warn)' }}>nenhum</span>
          )}
          <div className={styles.kind}>
            {p.models.length} modelo{p.models.length === 1 ? '' : 's'}
            {!p.has_credentials && <span style={{ color: 'var(--warn)' }}> · sem credenciais</span>}
          </div>
        </td>

        <td>
          <Tooltip content={status.title}>
            <span>
              <Badge tone={status.tone} label={status.label} />
            </span>
          </Tooltip>
          {p.last_status === 'error' && p.last_error && (
            /* Sem corte: a parte acionável de uma mensagem de erro costuma estar no fim.
               "...is deprecated for this mod" esconde justamente o que resolve. */
            <div className={styles.problem}>{p.last_error}</div>
          )}
        </td>

        <td>
          <div className={styles.actions}>
            <Tooltip content={blocked ?? (p.enabled ? 'Na cadeia de fallback.' : 'Fora da cadeia.')}>
              <span>
                <Switch
                  aria-label={`Ativar ${p.name}`}
                  checked={p.enabled}
                  disabled={!!blocked}
                  onCheckedChange={(v) => toggle.mutate(v)}
                />
              </span>
            </Tooltip>
            <Menu
              label={`Ações de ${p.name}`}
              actions={[
                { label: open ? 'Esconder modelos' : 'Modelos e preços', onSelect: () => setOpen((v) => !v) },
                {
                  label: test.isPending ? 'Testando…' : 'Testar agora',
                  onSelect: () => test.mutate(),
                  disabled: !!blocked || test.isPending,
                  hint: blocked,
                },
                { label: 'Editar credenciais', onSelect: onEdit },
                { label: 'Remover', onSelect: () => setConfirming(true), danger: true, separatorBefore: true },
              ]}
            />
          </div>
        </td>
      </tr>

      {open && (
        <tr className={styles.detail}>
          <td colSpan={5}>
            <ProviderModels provider={p} />
          </td>
        </tr>
      )}

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`Remover ${p.name}?`}
        description="O provedor sai da cadeia e seus modelos são apagados. As chamadas já registradas continuam no histórico de consumo."
        confirmLabel="Remover provedor"
        danger
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </>
  )
}
