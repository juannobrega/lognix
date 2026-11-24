import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { AiSettings } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import { SkeletonRows } from '../components/Skeleton'
import { useToast } from '../components/useToast'

export function AiSettingsPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const settings = useQuery({ queryKey: ['settings', 'ai'], queryFn: () => api<AiSettings>('/settings/ai') })
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [maxIn, setMaxIn] = useState(12000)
  const [maxOut, setMaxOut] = useState(1500)
  const [concurrency, setConcurrency] = useState(3)

  useEffect(() => {
    if (!settings.data) return
    setModel(settings.data.model ?? '')
    setMaxIn(settings.data.max_input_tokens)
    setMaxOut(settings.data.max_output_tokens)
    setConcurrency(settings.data.concurrency)
  }, [settings.data])

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
              color: s.active ? 'var(--ok)' : s.configured ? 'var(--warn)' : 'var(--fg-muted)',
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
            help="Identificador do modelo no OpenRouter. A lista com preços chega na fase 0.9.0."
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
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
              variant={s.enabled ? 'danger' : 'secondary'}
              disabled={!s.configured && !s.enabled}
              loading={save.isPending}
              onClick={() => save.mutate({ enabled: !s.enabled })}
            >
              {s.enabled ? 'Desativar IA' : 'Ativar IA'}
            </Button>
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
            A análise por IA entra na fase 0.9.0. Quando chegar, cada ocorrência detectada pelo ciclo vira um insight com resumo, causa
            provável, ação sugerida e as linhas que embasaram a conclusão. A IA nunca roda sozinha: só quando um trigger dispara.
          </p>
          <p className="muted" style={{ marginBottom: 0 }}>
            Toda chamada será registrada com modelo, tokens e custo, visíveis em Consumo.
          </p>
        </div>
      </section>
    </div>
  )
}
