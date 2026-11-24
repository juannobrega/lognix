import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { Insight } from '../api/types'
import { InsightCard } from './InsightCard'

const base: Insight = {
  id: 'i1',
  container_id: 'c1',
  container_name: 'api',
  host_name: 'vm-01',
  trigger_id: 't1',
  trigger_type: 'error',
  trigger_note: '2 linhas de erro',
  severity: 'high',
  title: 'Banco inacessível após redeploy',
  summary: 'O serviço perdeu a conexão com o Postgres.',
  probable_cause: 'DATABASE_URL aponta para host que não resolve.',
  suggested_action: 'Confira a variável na nova imagem.',
  confidence: 0.82,
  needs_code: false,
  evidence: [{ kind: 'log_line', index: 0, text: 'ERROR db down' }],
  code_diagnosis: null,
  context_truncated: false,
  status: 'new',
  seen_at: null,
  created_at: '2026-11-24T10:00:00Z',
}

function renderCard(insight: Insight) {
  return render(
    <MemoryRouter>
      <InsightCard insight={insight} />
    </MemoryRouter>,
  )
}

describe('InsightCard', () => {
  it('mostra severidade, projeto, título e confiança', () => {
    renderCard(base)
    expect(screen.getByText('alto')).toBeInTheDocument()
    expect(screen.getByText('api')).toBeInTheDocument()
    expect(screen.getByText('Banco inacessível após redeploy')).toBeInTheDocument()
    expect(screen.getByText(/confiança 82%/)).toBeInTheDocument()
    expect(screen.getByRole('link')).toHaveAttribute('href', '/insights/i1')
  })

  it('marca baixa confiança', () => {
    renderCard({ ...base, confidence: 0.2 })
    expect(screen.getByText(/confiança 20% · baixa/)).toBeInTheDocument()
  })

  it('avisa quando o contexto foi cortado e quando a causa é de código', () => {
    renderCard({ ...base, context_truncated: true, needs_code: true })
    expect(screen.getByText(/contexto cortado/)).toBeInTheDocument()
    expect(screen.getByText('causa provável no código')).toBeInTheDocument()
  })
})
