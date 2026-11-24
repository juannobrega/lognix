import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { AiModel, AiSettings, TestKeyResult } from '../api/types'
import { usd } from '../components/format'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import { SkeletonRows } from '../components/Skeleton'
import { useToast } from '../components/useToast'
import { Switch } from '../ui/Switch'

export function AiSettingsPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const settings = useQuery({ queryKey: ['settings', 'ai'], queryFn: () => api<AiSettings>('/settings/ai') })
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [maxIn, setMaxIn] = useState(12000)
  const [maxOut, setMaxOut] = useState(1500)
  const [concurrency, setConcurrency] = useState(3)
  const [modelQuery, setModelQuery] = useState('')
  const [showModels, setShowModels] = useState(false)

  useEffect(() => {
    if (!settings.data) return
    setModel(settings.data.model ?? '')
    setMaxIn(settings.data.max_input_tokens)
    setMaxOut(settings.data.max_output_tokens)
    setConcurrency(settings.data.concurrency)
  }, [settings.data])

  const models = useQuery({
    queryKey: ['settings', 'ai', 'models', modelQuery],
    queryFn: () => api<AiModel[]>(`/settings/ai/models?q=${encodeURIComponent(modelQuery)}`),
    enabled: showModels && !!settings.data?.has_api_key,
    retry: false,
  })

  const test = useMutation({
    mutationFn: () =>
      api<TestKeyResult>('/settings/ai/test', {
        method: 'POST',
        json: { api_key: apiKey || undefined, model: model || undefined },
      }),
    onSuccess: (r) =>
      r.ok
        ? toast.show(
            `Funcionou: ${r.model} respondeu em ${((r.latency_ms ?? 0) / 1000).toFixed(1)}s, custo ${usd(r.cost_usd ?? 0)}.`,
            'success',
          )
        : toast.show(r.error ?? 'O provider recusou.', 'error'),
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao testar.', 'error'),
  })

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<AiSettings>('/settings/ai', { method: 'PUT', json: body }),
    onSuccess: (data) => {
      setApiKey('')
      qc.setQueryData(['settings', 'ai'], data)
      void qc.invalidateQueries({ queryKey: ['summary'] })
      toast.show(
        data.active ? 'IA ativa.' : data.configured ? 'Configuração salva. Ative quando quiser.' : 'Configuração salva.',
        'success',
      )
    },
    onError: (e) =>
      toast.show(
        e instanceof ApiError ? [e.message, e.action].filter(Boolean).join(' ') : 'Falha ao salvar.',
        'error',
      ),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save.mutate({
      api_key: apiKey || undefined,
      model,
      max_input_tokens: maxIn,
      max_output_tokens: maxOut,
      concurrency,
    })
  }

  const s = settings.data
  if (!s) return <div className="card"><SkeletonRows rows={5} /></div>

  return (
    <div className="stack" style={{ maxWidth: 700 }}>
      <Alert
        kind="error"
        message="Trechos de log dos projetos monitorados são enviados ao OpenRouter e ao fabricante do modelo escolhido."
        action="Não ative em projetos cujos logs contenham dados que não podem sair do seu ambiente. Nenhuma redação automática é feita nesta versão."
      />

      <section className="card">
        <div className="card-header">
          <h2>Provider</h2>
          <span
            style={{
              fontSize: 'var(--text-sm)',
              fontWeight: 600,
              color: s.active ? 'var(--ok)' : s.configured ? 'var(--warn)' : 'var(--fg-dim)',
            }}
          >
            {s.active ? 'IA ativa' : s.configured ? 'configurada, desligada' : 'não configurada'}
          </span>
        </div>
        <form onSubmit={onSubmit} className="card-body">
          <Field
            label="Chave de API do OpenRouter"
            type="password"
            autoComplete="off"
            placeholder={s.has_api_key ? '•••••••• (uma chave já está salva)' : 'sk-or-...'}
            help={s.has_api_key ? 'Deixe em branco para manter a chave atual.' : 'A chave é guardada criptografada no banco.'}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <Field
            label="Modelo"
            placeholder="anthropic/claude-sonnet-4.5"
            help="Identificador do modelo no OpenRouter."
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
          {s.has_api_key && (
            <div style={{ marginBottom: 'var(--space-4)' }}>
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowModels((v) => !v)}>
                {showModels ? 'Esconder catálogo' : 'Escolher da lista do OpenRouter'}
              </Button>
              {showModels && (
                <div className="card" style={{ marginTop: 'var(--space-2)' }}>
                  <div style={{ padding: 'var(--space-3)' }}>
                    <input
                      aria-label="Buscar modelo"
                      placeholder="buscar modelo"
                      value={modelQuery}
                      onChange={(e) => setModelQuery(e.target.value)}
                      style={{ width: '100%' }}
                    />
                  </div>
                  {models.isError && <p className="muted" style={{ padding: '0 var(--space-3) var(--space-3)' }}>Não foi possível listar os modelos.</p>}
                  <div style={{ maxHeight: 280, overflow: 'auto' }}>
                    <table className="table">
                      <tbody>
                        {models.data?.slice(0, 60).map((m) => (
                          <tr key={m.id}>
                            <td>
                              <button
                                type="button"
                                onClick={() => {
                                  setModel(m.id)
                                  setShowModels(false)
                                }}
                                style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer', color: 'var(--accent)', textAlign: 'left' }}
                              >
                                {m.id}
                              </button>
                              <div className="muted" style={{ fontSize: 'var(--text-sm)' }}>{m.name}</div>
                            </td>
                            <td className="right muted" style={{ fontSize: 'var(--text-sm)', whiteSpace: 'nowrap' }}>
                              {m.prompt_usd_per_mtok !== null && m.completion_usd_per_mtok !== null
                                ? `$${m.prompt_usd_per_mtok.toFixed(2)} / $${m.completion_usd_per_mtok.toFixed(2)} por Mtok`
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)' }}>
            <Field label="Tokens de entrada" type="number" min={1000} max={200000} value={maxIn} onChange={(e) => setMaxIn(Number(e.target.value))} />
            <Field label="Tokens de saída" type="number" min={200} max={32000} value={maxOut} onChange={(e) => setMaxOut(Number(e.target.value))} />
            <Field label="Chamadas simultâneas" type="number" min={1} max={20} value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))} />
          </div>
          <div className="row">
            <Button type="submit" variant="primary" loading={save.isPending}>
              Salvar
            </Button>
            <Button
              type="button"
              onClick={() => test.mutate()}
              loading={test.isPending}
              disabled={!model || (!apiKey && !s.has_api_key)}
            >
              Testar
            </Button>
            <span className="row" style={{ gap: 'var(--space-3)', marginLeft: 'auto' }}>
              <label htmlFor="ai-enabled" style={{ margin: 0 }}>
                {s.enabled ? 'IA ligada' : 'IA desligada'}
              </label>
              <Switch
                id="ai-enabled"
                aria-label="Ativar a análise por IA"
                checked={s.enabled}
                disabled={!s.configured && !s.enabled}
                onCheckedChange={(v) => save.mutate({ enabled: v })}
              />
            </span>
            {!s.configured && (
              <span className="muted" style={{ fontSize: 'var(--text-sm)' }}>
                {s.enabled
                  ? 'O interruptor está ligado, mas falta chave ou modelo: a IA não roda.'
                  : 'Informe chave e modelo para poder ativar.'}
              </span>
            )}
          </div>
        </form>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>O que a IA fará</h2>
        </div>
        <div className="card-body">
          <p className="muted" style={{ marginTop: 0 }}>
            Cada ocorrência detectada pelo ciclo vira um insight com resumo, causa provável, ação sugerida e as linhas que embasaram a
            conclusão. A IA nunca roda sozinha: só quando um trigger dispara, e no máximo uma vez por ciclo por projeto.
          </p>
          <p className="muted" style={{ marginBottom: 0 }}>
            Resposta fora do formato esperado tem um retry; o segundo erro vira notificação e a ocorrência fica como "sem análise". Toda
            chamada é registrada com modelo, tokens e custo em <Link to="/settings/usage">Consumo</Link>.
          </p>
        </div>
      </section>
    </div>
  )
}
