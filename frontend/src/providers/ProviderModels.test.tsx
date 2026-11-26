import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Provider } from '../api/types'
import { ToastProvider } from '../components/Toast'
import { ProviderModels } from './ProviderModels'

const provider: Provider = {
  id: 'p1',
  kind: 'bedrock',
  label: 'Amazon Bedrock',
  name: 'Bedrock',
  enabled: true,
  priority: 1,
  default_model: 'anthropic.claude-sonnet-4-5-v1:0',
  credential_keys: ['region', 'access_key_id', 'secret_access_key'],
  has_credentials: true,
  last_status: 'ok',
  last_error: null,
  last_checked_at: null,
  paused_until: null,
  ready: true,
  models: [
    {
      id: 'm1',
      model_id: 'anthropic.claude-sonnet-4-5-v1:0',
      label: 'Claude Sonnet 4.5',
      enabled: true,
      context_length: 200000,
      prompt_usd_per_mtok: '3.0000',
      completion_usd_per_mtok: '15.0000',
    },
    {
      id: 'm2',
      model_id: 'meta.llama3-70b-instruct-v1:0',
      label: 'Llama 3 70B',
      enabled: false,
      context_length: null,
      prompt_usd_per_mtok: null,
      completion_usd_per_mtok: null,
    },
  ],
}

function renderModels(p: Provider) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <ProviderModels provider={p} />
      </ToastProvider>
    </QueryClientProvider>,
  )
}

describe('ProviderModels', () => {
  it('marca o modelo padrão e mostra o preço cadastrado', () => {
    renderModels(provider)
    expect(screen.getByText('PADRÃO')).toBeInTheDocument()
    expect(screen.getByText('$3,00/Mtok')).toBeInTheDocument()
    expect(screen.getByText('$15,00/Mtok')).toBeInTheDocument()
  })

  it('modelo sem preço cadastrado aparece como travessão, não como zero', () => {
    renderModels(provider)
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3)
  })

  it('não oferece tornar padrão para quem já é', async () => {
    renderModels(provider)
    await userEvent.click(screen.getByRole('button', { name: 'Ações de anthropic.claude-sonnet-4-5-v1:0' }))
    expect(screen.getByRole('menuitem', { name: 'Tornar padrão' })).toHaveAttribute('aria-disabled', 'true')
  })

  it('o cadastro à mão explica para que serve o preço', async () => {
    renderModels(provider)
    await userEvent.click(screen.getByRole('button', { name: 'À mão' }))
    expect(screen.getByLabelText('Identificador do modelo')).toBeInTheDocument()
    expect(screen.getByText(/estimar o custo quando o provedor não o informa/)).toBeInTheDocument()
  })

  it('sem credencial, o catálogo some e diz o motivo', () => {
    renderModels({ ...provider, has_credentials: false, credential_keys: [] })
    expect(screen.getByText('Salve as credenciais para ver o catálogo.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /catálogo de/ })).not.toBeInTheDocument()
  })
})
