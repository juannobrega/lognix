import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { AiSettings } from '../api/types'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import { SkeletonRows } from '../components/Skeleton'
import { useToast } from '../components/useToast'
import { Switch } from '../ui/Switch'

export function AiSettingsPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const settings = useQuery({ queryKey: ['settings', 'ai'], queryFn: () => api<AiSettings>('/settings/ai') })
  const [maxIn, setMaxIn] = useState(12000)
  const [maxOut, setMaxOut] = useState(1500)
  const [concurrency, setConcurrency] = useState(3)

  useEffect(() => {
    if (!settings.data) return
    setMaxIn(settings.data.max_input_tokens)
    setMaxOut(settings.data.max_output_tokens)
    setConcurrency(settings.data.concurrency)
  }, [settings.data])

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<AiSettings>('/settings/ai', { method: 'PUT', json: body }),
    onSuccess: (data, body) => {
      qc.setQueryData(['settings', 'ai'], data)
      void qc.invalidateQueries({ queryKey: ['summary'] })
      toast.show(
        'enabled' in body ? (data.active ? 'IA ativa.' : 'IA desligada.') : 'Limites salvos.',
        'success',
      )
    },
    onError: (e) => toast.show(e instanceof ApiError ? [e.message, e.action].filter(Boolean).join(' ') : 'Falha ao salvar.', 'error'),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save.mutate({ max_input_tokens: maxIn, max_output_tokens: maxOut, concurrency })
  }

  const s = settings.data
  if (!s) return <div className="card"><SkeletonRows rows={5} /></div>

  return (
    <div className="stack" style={{ maxWidth: 700 }}>
      <section className="card">
        <div className="card-header">
          <div>
            <h2>Análise por IA</h2>
            <p className="muted" style={{ margin: '2px 0 0', fontSize: 'var(--text-sm)' }}>
              {s.active
                ? `Ligada, com ${s.providers_ready} provedor(es) na cadeia.`
                : s.configured
                  ? 'Há provedor pronto, mas o interruptor está desligado: nenhuma chamada é feita.'
                  : s.providers > 0
                    ? 'Nenhum provedor cadastrado está pronto. Falta credencial, modelo padrão ou ativá-lo.'
                    : 'Nenhum provedor cadastrado.'}
            </p>
          </div>
          <span className="row" style={{ gap: 'var(--space-3)' }}>
            <label htmlFor="ai-enabled" style={{ margin: 0 }}>
              {s.enabled ? 'ligada' : 'desligada'}
            </label>
            <Switch
              id="ai-enabled"
              aria-label="Ativar a análise por IA"
              checked={s.enabled}
              disabled={!s.configured && !s.enabled}
              onCheckedChange={(v) => save.mutate({ enabled: v })}
            />
          </span>
        </div>
        <div className="card-body">
          <p className="muted" style={{ marginTop: 0 }}>
            Este é o interruptor geral. Credenciais, modelos e a ordem de fallback ficam em{' '}
            <Link to="/settings/providers">Provedores</Link>
            {s.providers === 0 ? ' — cadastre um para poder ligar a IA.' : '.'}
          </p>
          {s.enabled && !s.configured && (
            <p style={{ color: 'var(--warn)', marginBottom: 0, fontSize: 'var(--text-sm)' }}>
              O interruptor está ligado mas a cadeia está vazia: as ocorrências continuam sendo detectadas e ficam em Insights › Sem
              análise.
            </p>
          )}
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Limites por chamada</h2>
        </div>
        <form onSubmit={onSubmit} className="card-body">
          <p className="muted" style={{ marginTop: 0 }}>
            Valem para todos os provedores. O contexto é cortado no limite de entrada, e o insight registra quando isso aconteceu.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)' }}>
            <Field
              label="Tokens de entrada"
              type="number"
              min={1000}
              max={200000}
              value={maxIn}
              onChange={(e) => setMaxIn(Number(e.target.value))}
            />
            <Field label="Tokens de saída" type="number" min={200} max={32000} value={maxOut} onChange={(e) => setMaxOut(Number(e.target.value))} />
            <Field
              label="Chamadas simultâneas"
              type="number"
              min={1}
              max={20}
              value={concurrency}
              onChange={(e) => setConcurrency(Number(e.target.value))}
            />
          </div>
          <Button type="submit" variant="primary" loading={save.isPending}>
            Salvar
          </Button>
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
            Resposta fora do formato esperado tem um retry no mesmo provedor; falha de credencial, limite ou indisponibilidade desce a cadeia
            de fallback. Toda tentativa é registrada com provedor, modelo, tokens e custo em <Link to="/settings/usage">Consumo</Link>.
          </p>
        </div>
      </section>
    </div>
  )
}
