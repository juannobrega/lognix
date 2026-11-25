import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { Provider } from '../api/types'
import { ToastProvider } from '../components/Toast'
import { TooltipProvider } from '../ui/Tooltip'
import { ProviderCard } from './ProviderCard'

const base: Provider = {
  id: 'p1',
  kind: 'openrouter',
  label: 'OpenRouter',
  name: 'OpenRouter principal',
  enabled: true,
  priority: 1,
  default_model: 'anthropic/claude-sonnet-4.5',
  credential_keys: ['api_key'],
  has_credentials: true,
  last_status: 'ok',
  last_error: null,
  last_checked_at: '2026-11-24T10:00:00Z',
  paused_until: null,
  ready: true,
  models: [
    {
      id: 'm1',
      model_id: 'anthropic/claude-sonnet-4.5',
      label: 'Claude Sonnet 4.5',
      enabled: true,
      context_length: 200000,
      prompt_usd_per_mtok: '3.0000',
      completion_usd_per_mtok: '15.0000',
    },
  ],
}

function renderCard(provider: Provider, { index = 0, position = 0, total = 2 } = {}) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter>
            <ProviderCard provider={provider} index={index} position={position} total={total} onEdit={() => {}} onMove={() => {}} />
          </MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

describe('ProviderCard', () => {
  it('marca o primeiro da cadeia como principal e os seguintes como fallback', () => {
    renderCard(base)
    expect(screen.getByText('principal')).toBeInTheDocument()

    renderCard({ ...base, id: 'p2', name: 'Bedrock' }, { index: 2, position: 2, total: 3 })
    expect(screen.getByText('fallback 2')).toBeInTheDocument()
  })

  it('não dá posição de cadeia a quem não está pronto', () => {
    renderCard({ ...base, ready: false, enabled: false, has_credentials: false, credential_keys: [] }, { index: -1 })
    expect(screen.queryByText('principal')).not.toBeInTheDocument()
    expect(screen.getByText('sem credenciais')).toBeInTheDocument()
  })

  it('bloqueia testar e ativar sem credencial ou sem modelo padrão', () => {
    renderCard({ ...base, default_model: null, ready: false })
    expect(screen.getByRole('button', { name: 'Testar' })).toBeDisabled()
    expect(screen.getByRole('switch', { name: 'Ativar OpenRouter principal' })).toBeDisabled()
  })

  it('desabilita a seta de subir no topo e a de descer no fim', () => {
    renderCard(base, { position: 0, total: 2 })
    expect(screen.getByRole('button', { name: 'Subir na cadeia de fallback' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Descer na cadeia de fallback' })).toBeEnabled()
  })

  it('mostra o erro do último teste de quem está fora da cadeia', () => {
    renderCard({ ...base, ready: false, last_status: 'error', last_error: 'Chave recusada pelo provedor.' })
    expect(screen.getByText('Chave recusada pelo provedor.')).toBeInTheDocument()
    expect(screen.getByText('último teste falhou')).toBeInTheDocument()
  })

  it('pausado por limite de uso aparece como tal, não como erro', () => {
    renderCard({ ...base, paused_until: '2026-11-24T10:05:00Z' })
    expect(screen.getByText('pausado por limite de uso')).toBeInTheDocument()
  })
})
