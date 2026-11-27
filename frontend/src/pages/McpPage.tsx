import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, api } from '../api/client'
import type { McpCall, McpInfo, McpKey } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { CopyButton } from '../components/CopyButton'
import { EmptyState } from '../components/EmptyState'
import { dateTime } from '../components/format'
import { SkeletonRows } from '../components/Skeleton'
import { useToast } from '../components/useToast'
import { Icons } from '../layout/icons'
import { McpKeyDialog } from '../mcp/McpKeyDialog'
import styles from '../mcp/McpPage.module.css'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { Menu } from '../ui/Menu'
import { Switch } from '../ui/Switch'

const ROTULO: Record<string, string> = {
  leitura: 'Leitura',
  analise: 'Análise',
  admin: 'Administração',
}

/** Estado que interessa de relance: se a chave responde, e se alguém já a usou. */
function estado(k: McpKey): { texto: string; tom: string } {
  if (!k.enabled) return { texto: 'desativada', tom: styles.off }
  if (k.expires_at && new Date(k.expires_at) <= new Date()) return { texto: 'vencida', tom: styles.off }
  if (!k.last_used_at) return { texto: 'nunca usada', tom: styles.idle }
  return { texto: 'ativa', tom: styles.on }
}

export function McpPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const info = useQuery({
    queryKey: ['mcp', 'info'],
    queryFn: () => api<McpInfo>('/settings/mcp'),
    staleTime: Infinity,
  })
  const keys = useQuery({ queryKey: ['mcp', 'keys'], queryFn: () => api<McpKey[]>('/settings/mcp/keys') })
  const calls = useQuery({
    queryKey: ['mcp', 'calls'],
    queryFn: () => api<McpCall[]>('/settings/mcp/calls?limit=20'),
  })
  const [editando, setEditando] = useState<McpKey | undefined>()
  const [aberto, setAberto] = useState(false)
  const [revogando, setRevogando] = useState<McpKey | null>(null)

  const alternar = useMutation({
    mutationFn: (k: McpKey) =>
      api<McpKey>(`/settings/mcp/keys/${k.id}`, { method: 'PUT', json: { enabled: !k.enabled } }),
    onSuccess: (k) => {
      toast.show(k.enabled ? `${k.name} reativada.` : `${k.name} desativada.`, 'success')
      void qc.invalidateQueries({ queryKey: ['mcp', 'keys'] })
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao atualizar a chave.', 'error'),
  })

  const ligar = useMutation({
    mutationFn: (enabled: boolean) => api<McpInfo>('/settings/mcp', { method: 'PUT', json: { enabled } }),
    onSuccess: (r) => {
      toast.show(r.enabled ? 'Servidor MCP ligado.' : 'Servidor MCP desligado.', 'success')
      void qc.invalidateQueries({ queryKey: ['mcp', 'info'] })
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao mudar o interruptor.', 'error'),
  })

  const revogar = useMutation({
    mutationFn: (id: string) => api(`/settings/mcp/keys/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.show('Chave revogada.', 'success')
      setRevogando(null)
      void qc.invalidateQueries({ queryKey: ['mcp', 'keys'] })
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao revogar.', 'error'),
  })

  const url = info.data?.url ?? ''
  const comando = `claude mcp add --transport http lognix ${url} --header "Authorization: Bearer SUA_CHAVE"`

  return (
    <div className={styles.page}>
      <section className="card">
        <div className="card-header">
          <h2>Servidor MCP</h2>
          <span className={styles.switch}>
            <span className="muted">{info.data?.enabled ? 'ligado' : 'desligado'}</span>
            <Switch
              checked={info.data?.enabled ?? false}
              disabled={!info.data || info.data.managed || ligar.isPending}
              onCheckedChange={(v) => ligar.mutate(v)}
              aria-label="Servidor MCP"
            />
          </span>
        </div>
        <div className="card-body">
          {info.data?.managed ? (
            <Alert
              kind="info"
              message="mcp.enabled está declarado no config.yaml. Para ligar ou desligar pela tela, tire a chave do arquivo."
            />
          ) : info.data?.enabled === false ? (
            <Alert
              kind="warn"
              message="Desligado: o endereço /mcp responde 503 a todo mundo, com chave ou sem. As chaves continuam guardadas."
            />
          ) : info.data?.has_keys === false ? (
            <Alert kind="warn" message="Ligado, mas sem nenhuma chave ativa — ninguém consegue conectar ainda." />
          ) : null}
          <p className="muted">
            O Lognix atende o protocolo MCP neste endereço. Qualquer cliente compatível — Claude Code, Claude Desktop —
            passa a consultar hosts, logs e insights pelas ferramentas listadas abaixo, usando uma chave criada aqui.
          </p>
          <div className={styles.snippet}>
            <code>{url || '—'}</code>
            {url && <CopyButton value={url} />}
          </div>
          <p className="muted">Para o Claude Code, com a chave que você acabou de criar:</p>
          <div className={styles.snippet}>
            <code>{comando}</code>
            {url && <CopyButton value={comando} />}
          </div>
          <p className={styles.note}>
            Quem tem uma chave lê os logs que o Lognix guarda. Dê o escopo mínimo, e uma chave por cliente: é o que
            permite revogar um sem derrubar os outros.
          </p>
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Chaves</h2>
          <Button
            variant="primary"
            size="sm"
            disabled={!info.data}
            onClick={() => {
              setEditando(undefined)
              setAberto(true)
            }}
          >
            <Icons.plus width={14} height={14} />
            Nova chave
          </Button>
        </div>
        {keys.isPending ? (
          <div className="card-body">
            <SkeletonRows rows={3} />
          </div>
        ) : keys.data?.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Chave</th>
                <th>Permissões</th>
                <th>Estado</th>
                <th>Último uso</th>
                <th className="right">Chamadas</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {keys.data.map((k) => {
                const e = estado(k)
                return (
                  <tr key={k.id}>
                    <td style={{ fontWeight: 500 }}>{k.name}</td>
                    <td>
                      <code className={styles.prefix}>{k.prefix}…</code>
                    </td>
                    <td>
                      <span className={styles.scopes}>
                        {k.scopes.map((s) => (
                          <span key={s} className={styles.tag}>
                            {ROTULO[s] ?? s}
                          </span>
                        ))}
                      </span>
                    </td>
                    <td>
                      <span className={[styles.state, e.tom].join(' ')}>{e.texto}</span>
                    </td>
                    <td className="muted">{k.last_used_at ? dateTime(k.last_used_at) : '—'}</td>
                    <td className="right">{k.calls}</td>
                    <td className="right">
                      <Menu
                        label={`Ações de ${k.name}`}
                        actions={[
                          {
                            label: 'Editar permissões',
                            onSelect: () => {
                              setEditando(k)
                              setAberto(true)
                            },
                          },
                          { label: k.enabled ? 'Desativar' : 'Reativar', onSelect: () => alternar.mutate(k) },
                          {
                            label: 'Revogar',
                            danger: true,
                            separatorBefore: true,
                            onSelect: () => setRevogando(k),
                          },
                        ]}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ) : (
          <div className="card-body">
            <EmptyState title="Nenhuma chave ainda">
              <p className="muted">
                Sem chave, o endereço MCP responde 401 a todo mundo. Crie uma por cliente que for conectar.
              </p>
            </EmptyState>
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Ferramentas</h2>
          <span className="muted">{info.data?.tools.length ?? 0} disponíveis</span>
        </div>
        {info.data ? (
          <table className="table">
            <thead>
              <tr>
                <th>Ferramenta</th>
                <th>Exige</th>
                <th>O que faz</th>
              </tr>
            </thead>
            <tbody>
              {info.data.tools.map((t) => (
                <tr key={t.nome}>
                  <td>
                    <code className={styles.prefix}>{t.nome}</code>
                  </td>
                  <td>
                    <span className={styles.tag}>{ROTULO[t.escopo] ?? t.escopo}</span>
                  </td>
                  <td className="muted">{t.descricao}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="card-body">
            <SkeletonRows rows={4} />
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Chamadas recentes</h2>
        </div>
        {calls.data?.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Quando</th>
                <th>Chave</th>
                <th>Ferramenta</th>
                <th>Resultado</th>
                <th className="right">Duração</th>
              </tr>
            </thead>
            <tbody>
              {calls.data.map((c) => (
                <tr key={c.id}>
                  <td className="muted">{dateTime(c.created_at)}</td>
                  <td>{c.key_name}</td>
                  <td>
                    <code className={styles.prefix}>{c.tool}</code>
                  </td>
                  <td>
                    {c.ok ? (
                      <span className={[styles.state, styles.on].join(' ')}>ok</span>
                    ) : (
                      <span className={styles.failure} title={c.error ?? undefined}>
                        {c.error ?? 'erro'}
                      </span>
                    )}
                  </td>
                  <td className="right muted">{c.duration_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="card-body">
            <EmptyState title="Nenhuma chamada registrada">
              <p className="muted">
                Toda chamada de ferramenta fica aqui, com a chave que a fez. É por esta lista que se descobre uma chave
                vazada.
              </p>
            </EmptyState>
          </div>
        )}
      </section>

      {info.data && <McpKeyDialog info={info.data} chave={editando} open={aberto} onOpenChange={setAberto} />}
      {revogando && (
        <ConfirmDialog
          open
          onOpenChange={(v) => !v && setRevogando(null)}
          title={`Revogar ${revogando.name}?`}
          description="O cliente que usa esta chave para de responder na hora. O histórico de chamadas continua aqui."
          confirmLabel="Revogar chave"
          danger
          loading={revogar.isPending}
          onConfirm={() => revogar.mutate(revogando.id)}
        />
      )}
    </div>
  )
}
