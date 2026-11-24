import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { AiSettings, Summary } from '../api/types'
import { EmptyState } from '../components/EmptyState'
import { compact } from '../components/format'
import { Stat, StatGrid } from '../components/Stat'

export function UsagePage() {
  const ai = useQuery({ queryKey: ['settings', 'ai'], queryFn: () => api<AiSettings>('/settings/ai') })
  const summary = useQuery({ queryKey: ['summary'], queryFn: () => api<Summary>('/summary') })

  return (
    <div className="stack" style={{ maxWidth: 900 }}>
      <section className="card">
        <div className="card-header">
          <h2>Consumo de IA</h2>
          <span className="muted" style={{ fontSize: 'var(--text-sm)' }}>provider: {ai.data?.provider ?? '—'}</span>
        </div>
        <div className="card-body">
          <StatGrid>
            <Stat value="$0,00" label="Gasto hoje" />
            <Stat value="$0,00" label="Gasto nos últimos 30 dias" />
            <Stat value="0" label="Chamadas" />
            <Stat value="0" label="Tokens" />
          </StatGrid>
        </div>
      </section>

      <EmptyState title="Nenhuma chamada de IA ainda">
        <p>
          {ai.data?.active
            ? 'A IA está ativa. As chamadas começam quando a análise por IA entrar, na fase 0.9.0.'
            : ai.data?.configured
              ? 'A IA está configurada mas desligada. Ative em Configurações › IA.'
              : 'Configure um provider em Configurações › IA para começar.'}
        </p>
        {summary.data && summary.data.triggers_unanalyzed > 0 && (
          <p className="muted">
            Há {compact(summary.data.triggers_unanalyzed)} ocorrências aguardando análise.{' '}
            <Link to="/insights">Ver ocorrências</Link>
          </p>
        )}
      </EmptyState>

      <section className="card">
        <div className="card-header">
          <h2>Como o custo será contado</h2>
        </div>
        <div className="card-body">
          <p className="muted" style={{ marginTop: 0 }}>
            Cada chamada registra modelo, tokens de entrada e saída, custo, latência e o trigger que a originou. O custo vem da resposta do
            OpenRouter quando ele o informa; caso contrário é estimado pela tabela de preços do modelo.
          </p>
          <p className="muted" style={{ marginBottom: 0 }}>
            Nesta versão não há orçamento com bloqueio: você vê o gasto, mas o Lognix não para de chamar sozinho.
          </p>
        </div>
      </section>
    </div>
  )
}
