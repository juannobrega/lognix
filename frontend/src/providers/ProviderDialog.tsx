import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { Provider, ProviderKind, ProviderKindInfo } from '../api/types'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import { useToast } from '../components/useToast'
import dialog from '../ui/Dialog.module.css'
import { Select } from '../ui/Select'
import { ProviderIcon } from './icons'
import { PROVIDER_TINT } from './kinds'
import styles from './ProviderDialog.module.css'

interface Props {
  /** Ausente: diálogo de cadastro. Presente: edição daquele provedor. */
  provider?: Provider
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Chamado com o provedor salvo, para a verificação em etapas emendar no cadastro. */
  onSaved?: (provider: Provider) => void
}

export function ProviderDialog({ provider, open, onOpenChange, onSaved }: Props) {
  const qc = useQueryClient()
  const toast = useToast()
  const editing = provider !== undefined
  const kinds = useQuery({
    queryKey: ['providers', 'kinds'],
    queryFn: () => api<ProviderKindInfo[]>('/settings/ai/providers/kinds'),
    staleTime: Infinity,
  })

  const [kind, setKind] = useState<ProviderKind>(provider?.kind ?? 'openrouter')
  const [name, setName] = useState(provider?.name ?? '')
  const [defaultModel, setDefaultModel] = useState(provider?.default_model ?? '')
  const [creds, setCreds] = useState<Record<string, string>>({})

  // Reabrir o diálogo recomeça do estado do provedor, não do que ficou da última vez.
  useEffect(() => {
    if (!open) return
    setKind(provider?.kind ?? 'openrouter')
    setName(provider?.name ?? '')
    setDefaultModel(provider?.default_model ?? '')
    setCreds({})
  }, [open, provider])

  const info = kinds.data?.find((k) => k.kind === kind)

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      editing
        ? api<Provider>(`/settings/ai/providers/${provider.id}`, { method: 'PUT', json: body })
        : api<Provider>('/settings/ai/providers', { method: 'POST', json: body }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['providers'] })
      void qc.invalidateQueries({ queryKey: ['settings', 'ai'] })
      void qc.invalidateQueries({ queryKey: ['summary'] })
      toast.show(editing ? `${r.name} atualizado.` : `${r.name} cadastrado.`, 'success')
      onOpenChange(false)
      onSaved?.(r)
    },
    onError: (e) => toast.show(e instanceof ApiError ? [e.message, e.action].filter(Boolean).join(' ') : 'Falha ao salvar.', 'error'),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    const filled = Object.fromEntries(Object.entries(creds).filter(([, v]) => v !== ''))
    save.mutate(
      editing
        ? { name: name.trim(), default_model: defaultModel.trim() || null, credentials: filled }
        : { kind, name: name.trim(), default_model: defaultModel.trim() || null, credentials: filled },
    )
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className={dialog.overlay} />
        <Dialog.Content className={dialog.content} style={{ maxWidth: 560 }}>
          <Dialog.Title className={dialog.title}>{editing ? `Editar ${provider.name}` : 'Novo provedor'}</Dialog.Title>
          <form onSubmit={onSubmit}>
            {!editing ? (
              <div className={styles.field}>
                <label htmlFor="provider-kind">Tipo</label>
                <Select
                  id="provider-kind"
                  aria-label="Tipo de provedor"
                  value={kind}
                  options={(kinds.data ?? []).map((k) => ({
                    value: k.kind,
                    label: (
                      <span className={styles.option}>
                        <span className={styles.glyph} style={{ ['--tint' as string]: PROVIDER_TINT[k.kind] }}>
                          <ProviderIcon kind={k.kind} width={16} height={16} />
                        </span>
                        {k.label}
                      </span>
                    ),
                  }))}
                  onValueChange={(v) => {
                    const next = v as ProviderKind
                    const previous = kinds.data?.find((k) => k.kind === kind)
                    setKind(next)
                    setCreds({})
                    // Trocar de tipo renomeia só enquanto o nome ainda é o que nós sugerimos.
                    if (!name.trim() || name === previous?.label) {
                      setName(kinds.data?.find((k) => k.kind === next)?.label ?? '')
                    }
                  }}
                />
                <span className={styles.help}>Define quais credenciais o provedor pede.</span>
              </div>
            ) : (
              <div className={styles.current}>
                <span className={styles.glyph} style={{ ['--tint' as string]: PROVIDER_TINT[kind] }}>
                  <ProviderIcon kind={kind} width={16} height={16} />
                </span>
                {provider.label}
                <span className={styles.help}>o tipo não muda depois de cadastrado</span>
              </div>
            )}

            <Field
              label="Nome"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={info?.label ?? 'OpenRouter'}
              help="Como este provedor aparece na cadeia de fallback. Útil quando há duas contas do mesmo tipo."
              required
            />

            {info?.fields.map((f) => (
              <Field
                key={f.key}
                label={f.label}
                type={f.secret ? 'password' : 'text'}
                autoComplete="off"
                placeholder={provider?.credential_keys.includes(f.key) ? '•••••••• (um valor já está salvo)' : f.placeholder}
                help={
                  provider?.credential_keys.includes(f.key)
                    ? 'Em branco mantém o valor atual.'
                    : f.help || (f.required ? undefined : 'Opcional.')
                }
                value={creds[f.key] ?? ''}
                onChange={(e) => setCreds({ ...creds, [f.key]: e.target.value })}
                required={f.required && !editing}
              />
            ))}

            <Field
              label="Modelo padrão"
              value={defaultModel}
              onChange={(e) => setDefaultModel(e.target.value)}
              placeholder={kind === 'bedrock' ? 'anthropic.claude-sonnet-4-5-20250929-v1:0' : 'anthropic/claude-sonnet-4.5'}
              help={
                editing
                  ? 'O modelo usado quando este provedor é chamado. Dá para trocar pela lista de modelos do cartão.'
                  : 'Dá para deixar em branco agora e escolher pelo catálogo depois de salvar as credenciais.'
              }
            />

            <div className={dialog.actions}>
              <Dialog.Close asChild>
                <Button type="button">Cancelar</Button>
              </Dialog.Close>
              <Button type="submit" variant="primary" loading={save.isPending} disabled={!name.trim()}>
                {editing ? 'Salvar' : 'Cadastrar'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
