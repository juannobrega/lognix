import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { Provider, ProviderKind, ProviderKindInfo } from '../api/types'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import { useToast } from '../components/useToast'
import dialog from '../ui/Dialog.module.css'
import { ProviderIcon } from './icons'
import { PROVIDER_TINT } from './kinds'
import styles from './ProviderDialog.module.css'

interface Props {
  /** Ausente: diálogo de cadastro. Presente: edição daquele provedor. */
  provider?: Provider
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ProviderDialog({ provider, open, onOpenChange }: Props) {
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
      toast.show(editing ? `${r.name} atualizado.` : `${r.name} cadastrado. Cadastre um modelo e teste.`, 'success')
      onOpenChange(false)
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
            {!editing && (
              <div className={styles.kinds} role="radiogroup" aria-label="Tipo de provedor">
                {kinds.data?.map((k) => (
                  <button
                    type="button"
                    key={k.kind}
                    role="radio"
                    aria-checked={kind === k.kind}
                    className={styles.kind}
                    style={{ ['--tint' as string]: PROVIDER_TINT[k.kind] }}
                    onClick={() => {
                      setKind(k.kind)
                      setCreds({})
                      if (!name.trim()) setName(k.label)
                    }}
                  >
                    <ProviderIcon kind={k.kind} width={22} height={22} />
                    <span>{k.label}</span>
                  </button>
                ))}
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
