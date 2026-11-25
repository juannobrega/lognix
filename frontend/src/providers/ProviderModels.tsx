import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, api } from '../api/client'
import type { CatalogModel, Provider, ProviderModel } from '../api/types'
import { Button } from '../components/Button'
import { usd } from '../components/format'
import { useToast } from '../components/useToast'
import { Combobox, type ComboboxOption } from '../ui/Combobox'
import { Menu } from '../ui/Menu'
import styles from './ProviderModels.module.css'

function price(value: string | number | null): string {
  if (value === null || value === '') return '—'
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? `${usd(n)}/Mtok` : '—'
}

export function ProviderModels({ provider }: { provider: Provider }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [manual, setManual] = useState<{ model_id: string; prompt: string; completion: string } | null>(null)

  const invalidate = () => void qc.invalidateQueries({ queryKey: ['providers'] })

  const catalog = useQuery({
    queryKey: ['providers', provider.id, 'catalog'],
    queryFn: () => api<CatalogModel[]>(`/settings/ai/providers/${provider.id}/catalog`),
    enabled: provider.has_credentials,
    retry: false,
    staleTime: 5 * 60_000,
  })

  const addModel = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Provider>(`/settings/ai/providers/${provider.id}/models`, { method: 'POST', json: body }),
    onSuccess: (_r, body) => {
      toast.show(`${String(body.model_id)} cadastrado.`, 'success')
      setManual(null)
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

  const options: ComboboxOption[] = (catalog.data ?? [])
    .filter((m) => !m.already_added)
    .map((m) => ({
      value: m.id,
      label: m.id,
      hint:
        m.prompt_usd_per_mtok !== null && m.prompt_usd_per_mtok > 0
          ? `${usd(m.prompt_usd_per_mtok)} / ${usd(m.completion_usd_per_mtok ?? 0)}`
          : undefined,
    }))

  function addFromCatalog(id: string) {
    const m = catalog.data?.find((c) => c.id === id)
    addModel.mutate({
      model_id: id,
      label: m?.name ?? '',
      context_length: m?.context_length ?? undefined,
      prompt_usd_per_mtok: m?.prompt_usd_per_mtok ?? undefined,
      completion_usd_per_mtok: m?.completion_usd_per_mtok ?? undefined,
    })
  }

  return (
    <div className={styles.panel}>
      <div className={styles.bar}>
        <h3 className={styles.heading}>Modelos cadastrados</h3>
        <div className={styles.pick}>
          {provider.has_credentials ? (
            <Combobox
              aria-label={`Cadastrar um modelo do catálogo de ${provider.name}`}
              options={options}
              onSelect={addFromCatalog}
              placeholder={catalog.isError ? 'catálogo indisponível' : 'cadastrar do catálogo'}
              searchPlaceholder="buscar modelo"
              loading={catalog.isPending}
              disabled={catalog.isError || catalog.isPending}
              emptyLabel={options.length === 0 ? 'Todos os modelos do catálogo já estão cadastrados.' : 'Nenhum modelo com esse nome.'}
            />
          ) : (
            <span className={styles.note}>Salve as credenciais para ver o catálogo.</span>
          )}
          <Button size="sm" onClick={() => setManual({ model_id: '', prompt: '', completion: '' })}>
            À mão
          </Button>
          {provider.models.length > 0 && provider.has_credentials && (
            <Button size="sm" variant="ghost" onClick={() => syncPrices.mutate()} loading={syncPrices.isPending}>
              Atualizar preços
            </Button>
          )}
        </div>
      </div>

      {catalog.isError && <p className={styles.note}>O catálogo não respondeu: {(catalog.error as ApiError).message}</p>}

      {manual && (
        <form
          className={styles.manual}
          onSubmit={(e) => {
            e.preventDefault()
            addModel.mutate({
              model_id: manual.model_id.trim(),
              prompt_usd_per_mtok: manual.prompt ? Number(manual.prompt) : undefined,
              completion_usd_per_mtok: manual.completion ? Number(manual.completion) : undefined,
            })
          }}
        >
          <div className={styles.manualGrid}>
            <div>
              <label htmlFor="mid">Identificador do modelo</label>
              <input id="mid" autoFocus value={manual.model_id} onChange={(e) => setManual({ ...manual, model_id: e.target.value })} required />
            </div>
            <div>
              <label htmlFor="mp">Entrada $/Mtok</label>
              <input id="mp" type="number" step="0.01" min="0" value={manual.prompt} onChange={(e) => setManual({ ...manual, prompt: e.target.value })} />
            </div>
            <div>
              <label htmlFor="mc">Saída $/Mtok</label>
              <input
                id="mc"
                type="number"
                step="0.01"
                min="0"
                value={manual.completion}
                onChange={(e) => setManual({ ...manual, completion: e.target.value })}
              />
            </div>
            <Button type="submit" variant="primary" loading={addModel.isPending}>
              Cadastrar
            </Button>
            <Button type="button" onClick={() => setManual(null)}>
              Cancelar
            </Button>
          </div>
          <p className={styles.note}>
            Para o que o catálogo não lista: um perfil de inferência do Bedrock, um deployment. O preço é usado para estimar o custo quando o
            provedor não o informa.
          </p>
        </form>
      )}

      {provider.models.length === 0 ? (
        <p className={styles.note}>Nenhum modelo cadastrado. Escolha um do catálogo ou adicione à mão.</p>
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
              <tr key={m.id} className={m.enabled ? undefined : styles.off}>
                <td>
                  <span className="mono">{m.model_id}</span>
                  {provider.default_model === m.model_id && <span className={styles.default}>PADRÃO</span>}
                </td>
                <td className="num">{price(m.prompt_usd_per_mtok)}</td>
                <td className="num">{price(m.completion_usd_per_mtok)}</td>
                <td className="num muted">{m.context_length ? `${Math.round(m.context_length / 1000)}k` : '—'}</td>
                <td className="right">
                  <Menu
                    label={`Ações de ${m.model_id}`}
                    actions={[
                      {
                        label: 'Tornar padrão',
                        onSelect: () => setDefault.mutate(m.model_id),
                        disabled: provider.default_model === m.model_id,
                        hint: 'Já é o modelo padrão.',
                      },
                      { label: m.enabled ? 'Desativar' : 'Ativar', onSelect: () => updateModel.mutate({ id: m.id, body: { enabled: !m.enabled } }) },
                      { label: 'Remover', onSelect: () => removeModel.mutate(m.id), danger: true, separatorBefore: true },
                    ]}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
