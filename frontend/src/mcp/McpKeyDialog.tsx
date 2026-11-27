import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { McpInfo, McpKey, McpScopeName } from '../api/types'
import { Button } from '../components/Button'
import { CopyButton } from '../components/CopyButton'
import { Field } from '../components/Field'
import { useToast } from '../components/useToast'
import dialog from '../ui/Dialog.module.css'
import { Select } from '../ui/Select'
import styles from './McpKeyDialog.module.css'

interface Props {
  info: McpInfo
  /** Ausente: criar. Presente: editar nome e escopos daquela chave. */
  chave?: McpKey
  open: boolean
  onOpenChange: (open: boolean) => void
}

const PRAZOS = [
  { value: '0', label: 'Sem expiração' },
  { value: '30', label: '30 dias' },
  { value: '90', label: '90 dias' },
  { value: '365', label: '1 ano' },
]

export function McpKeyDialog({ info, chave, open, onOpenChange }: Props) {
  const qc = useQueryClient()
  const toast = useToast()
  const editando = chave !== undefined
  const [nome, setNome] = useState('')
  const [escopos, setEscopos] = useState<McpScopeName[]>(['leitura'])
  const [prazo, setPrazo] = useState('0')
  const [criada, setCriada] = useState<McpKey | null>(null)

  // Reabrir recomeça do estado da chave, não do que ficou da última vez.
  useEffect(() => {
    if (!open) return
    setNome(chave?.name ?? '')
    setEscopos(chave?.scopes ?? ['leitura'])
    setPrazo('0')
    setCriada(null)
  }, [open, chave])

  const salvar = useMutation({
    mutationFn: () =>
      editando
        ? api<McpKey>(`/settings/mcp/keys/${chave.id}`, {
            method: 'PUT',
            json: { name: nome.trim(), scopes: escopos },
          })
        : api<McpKey>('/settings/mcp/keys', {
            method: 'POST',
            json: {
              name: nome.trim(),
              scopes: escopos,
              expires_in_days: prazo === '0' ? null : Number(prazo),
            },
          }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['mcp', 'keys'] })
      if (editando) {
        toast.show(`${r.name} atualizada.`, 'success')
        onOpenChange(false)
        return
      }
      // Não fecha: esta é a única vez que a chave existe em texto legível.
      setCriada(r)
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao salvar a chave.', 'error'),
  })

  function alternar(escopo: McpScopeName) {
    setEscopos((atual) => (atual.includes(escopo) ? atual.filter((e) => e !== escopo) : [...atual, escopo]))
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    salvar.mutate()
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className={dialog.overlay} />
        <Dialog.Content className={dialog.content} style={{ maxWidth: 560 }}>
          {criada ? (
            <>
              <Dialog.Title className={dialog.title}>{criada.name}</Dialog.Title>
              <Dialog.Description className={dialog.description}>
                Guarde a chave agora. O Lognix só tem o hash dela — não há como mostrar de novo, só criar outra.
              </Dialog.Description>
              <div className={styles.secret}>
                <code>{criada.secret}</code>
                <CopyButton value={criada.secret ?? ''} />
              </div>
              <p className={styles.legend}>No cliente MCP, aponte para {info.url} com esta chave no cabeçalho:</p>
              <div className={styles.secret}>
                <code>Authorization: Bearer {criada.secret}</code>
                <CopyButton value={`Bearer ${criada.secret ?? ''}`} />
              </div>
              <div className={dialog.actions}>
                <Button variant="primary" onClick={() => onOpenChange(false)}>
                  Já guardei
                </Button>
              </div>
            </>
          ) : (
            <>
              <Dialog.Title className={dialog.title}>
                {editando ? `Editar ${chave.name}` : 'Nova chave MCP'}
              </Dialog.Title>
              <form onSubmit={onSubmit}>
                <Field
                  label="Nome"
                  value={nome}
                  onChange={(e) => setNome(e.target.value)}
                  placeholder="Claude Code do meu notebook"
                  help="Diz de quem é a chave. É por ele que você vai saber qual revogar."
                  required
                  maxLength={80}
                  autoFocus
                />

                <p className={styles.legend}>Permissões</p>
                <div className={styles.scopes}>
                  {info.scopes.map((s) => (
                    <label key={s.nome} className={styles.scope}>
                      <input type="checkbox" checked={escopos.includes(s.nome)} onChange={() => alternar(s.nome)} />
                      <span>
                        <strong>{s.rotulo}</strong>
                        <span>{s.descricao}</span>
                        <span className={styles.risk}>{s.risco}</span>
                      </span>
                    </label>
                  ))}
                </div>

                {!editando && (
                  <div className={styles.prazo}>
                    <label htmlFor="mcp-prazo">Validade</label>
                    <Select
                      id="mcp-prazo"
                      aria-label="Validade da chave"
                      value={prazo}
                      options={PRAZOS}
                      onValueChange={setPrazo}
                    />
                  </div>
                )}

                <div className={dialog.actions}>
                  <Button type="button" onClick={() => onOpenChange(false)}>
                    Cancelar
                  </Button>
                  <Button type="submit" variant="primary" loading={salvar.isPending} disabled={escopos.length === 0}>
                    {editando ? 'Salvar' : 'Criar chave'}
                  </Button>
                </div>
              </form>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
