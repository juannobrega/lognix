import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, api } from '../api/client'
import type { CatalogModel, Provider, ProviderModel } from '../api/types'
import { Button } from '../components/Button'
import { usd } from '../components/format'
import { SkeletonRows } from '../components/Skeleton'
import { useToast } from '../components/useToast'

function price(value: string | number | null): string {
  if (value === null || value === '') return '—'
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? `${usd(n)}/Mtok` : '—'
}

export function ProviderModels({ provider }: { provider: Provider }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [tab, setTab] = useState<'added' | 'catalog' | 'manual'>('added')
  const [query, setQuery] = useState('')
  const [manual, setManual] = useState({ model_id: '', prompt: '', completion: '' })

  const invalidate = () => void qc.invalidateQueries({ queryKey: ['providers'] })

  const catalog = useQuery({
    queryKey: ['providers', provider.id, 'catalog', query],
    queryFn: () => api<CatalogModel[]>(`/settings/ai/providers/${provider.id}/catalog?q=${encodeURIComponent(query)}`),
    enabled: tab === 'catalog' && provider.has_credentials,
    retry: false,
  })

  const addModel = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Provider>(`/settings/ai/providers/${provider.id}/models`, { method: 'POST', json: body }),
    onSuccess: () => {
      toast.show('Modelo cadastrado.', 'success')
      setManual({ model_id: '', prompt: '', completion: '' })
      invalidate()
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao cadastrar.', 'error'),
  })

  const updateModel = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api<Provider>(`/settings/ai/providers/${provider.id}/models/${id}`, { method: 'PUT', json: body }),
    onSuccess: invalidate,
  })

  const removeModel = useMutation({
    mutationFn: (id: string) => api<Provider>(`/settings/ai/providers/${provider.id}/models/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.show('Modelo removido.', 'success')
      invalidate()
    },
  })

  const setDefault = useMutation({
    mutationFn: (modelId: string) => api<Provider>(`/settings/ai/providers/${provider.id}`, { method: 'PUT', json: { default_model: modelId } }),
    onSuccess: (r) => {
      toast.show(`${r.default_model} virou o modelo padrão de ${r.name}.`, 'success')
      invalidate()
    },
  })

  const syncPrices = useMutation({
    mutationFn: () => api<Provider>(`/settings/ai/providers/${provider.id}/catalog/sync`, { method: 'POST' }),
    onSuccess: () => {
      toast.show('Preços e janelas de contexto atualizados pelo catálogo.', 'success')
      invalidate()
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao sincronizar.', 'error'),
  })

  return (
    <div className="card" style={{ background: 'var(--canvas)' }}>
      <div className="card-header">
        <div role="tablist" className="tabs" style={{ margin: 0, border: 0 }}>
          {(['added', 'catalog', 'manual'] as const).map((t) => (
            <button key={t} role="tab" className="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
              {{ added: `Cadastrados (${provider.models.length})`, catalog: 'Catálogo', manual: 'Adicionar à mão' }[t]}
            </button>
          ))}
        </div>
        {tab === 'added' && provider.models.length > 0 && provider.has_credentials && (
          <Button size="sm" variant="ghost" onClick={() => syncPrices.mutate()} loading={syncPrices.isPending}>
            Atualizar preços
          </Button>
        )}
      </div>

      {tab === 'added' &&
        (provider.models.length === 0 ? (
          <p className="muted card-body" style={{ margin: 0 }}>
            Nenhum modelo cadastrado. Use o catálogo ou adicione à mão.
          </p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Modelo</th>
                <th className="num">Entrada</th>
                <th className="num">Saída</th>
                <th className="num">Contexto</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {provider.models.map((m: ProviderModel) => (
                <tr key={m.id} style={{ opacity: m.enabled ? 1 : 0.5 }}>
                  <td>
                    <span className="mono">{m.model_id}</span>
                    {provider.default_model === m.model_id && (
                      <span style={{ color: 'var(--accent)', marginLeft: 8, fontSize: 'var(--text-meta)', fontWeight: 600 }}>PADRÃO</span>
                    )}
                  </td>
                  <td className="num">{price(m.prompt_usd_per_mtok)}</td>
                  <td className="num">{price(m.completion_usd_per_mtok)}</td>
                  <td className="num muted">{m.context_length ? `${Math.round(m.context_length / 1000)}k` : '—'}</td>
                  <td className="right">
                    <span className="row" style={{ justifyContent: 'flex-end', flexWrap: 'nowrap' }}>
                      {provider.default_model !== m.model_id && (
                        <Button size="sm" variant="ghost" onClick={() => setDefault.mutate(m.model_id)}>
                          Tornar padrão
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => updateModel.mutate({ id: m.id, body: { enabled: !m.enabled } })}>
                        {m.enabled ? 'Desativar' : 'Ativar'}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => removeModel.mutate(m.id)}>
                        Remover
                      </Button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}

      {tab === 'catalog' && (
        <>
          <div style={{ padding: 'var(--space-3) var(--space-5)' }}>
            <input aria-label="Buscar no catálogo" placeholder="buscar modelo" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          {!provider.has_credentials && (
            <p className="muted card-body" style={{ margin: 0 }}>
              Salve as credenciais para ver o catálogo deste provedor.
            </p>
          )}
          {catalog.isPending && provider.has_credentials && <SkeletonRows rows={3} />}
          {catalog.isError && (
            <p className="card-body" style={{ margin: 0, color: 'var(--error)' }}>
              {(catalog.error as ApiError).message}
            </p>
          )}
          {catalog.data && (
            <div style={{ maxHeight: 320, overflow: 'auto' }}>
              <table className="table">
                <tbody>
                  {catalog.data.slice(0, 80).map((m) => (
                    <tr key={m.id}>
                      <td>
                        <span className="mono">{m.id}</span>
                        <div className="meta">{m.name}</div>
                      </td>
                      <td className="num muted">
                        {m.prompt_usd_per_mtok !== null && m.prompt_usd_per_mtok > 0
                          ? `${usd(m.prompt_usd_per_mtok)} / ${usd(m.completion_usd_per_mtok ?? 0)}`
                          : '—'}
                      </td>
                      <td className="right">
                        {m.already_added ? (
                          <span className="muted">cadastrado</span>
                        ) : (
                          <Button
                            size="sm"
                            onClick={() =>
                              addModel.mutate({
                                model_id: m.id,
                                label: m.name,
                                context_length: m.context_length ?? undefined,
                                prompt_usd_per_mtok: m.prompt_usd_per_mtok ?? undefined,
                                completion_usd_per_mtok: m.completion_usd_per_mtok ?? undefined,
                              })
                            }
                          >
                            Cadastrar
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {tab === 'manual' && (
        <form
          className="card-body"
          onSubmit={(e) => {
            e.preventDefault()
            addModel.mutate({
              model_id: manual.model_id.trim(),
              prompt_usd_per_mtok: manual.prompt ? Number(manual.prompt) : undefined,
              completion_usd_per_mtok: manual.completion ? Number(manual.completion) : undefined,
            })
          }}
        >
          <p className="muted" style={{ marginTop: 0 }}>
            Para modelos que o catálogo não lista, como um perfil de inferência do Bedrock ou um deployment do Azure. O preço é usado para
            estimar o custo quando o provedor não o informa.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr auto', gap: 'var(--space-3)', alignItems: 'end' }}>
            <div>
              <label htmlFor="mid">Identificador do modelo</label>
              <input id="mid" value={manual.model_id} onChange={(e) => setManual({ ...manual, model_id: e.target.value })} required />
            </div>
            <div>
              <label htmlFor="mp">Entrada $/Mtok</label>
              <input id="mp" type="number" step="0.01" min="0" value={manual.prompt} onChange={(e) => setManual({ ...manual, prompt: e.target.value })} />
            </div>
            <div>
              <label htmlFor="mc">Saída $/Mtok</label>
              <input id="mc" type="number" step="0.01" min="0" value={manual.completion} onChange={(e) => setManual({ ...manual, completion: e.target.value })} />
            </div>
            <Button type="submit" variant="primary" loading={addModel.isPending}>
              Cadastrar
            </Button>
          </div>
        </form>
      )}
    </div>
  )
}
