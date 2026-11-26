import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { Provider } from '../api/types'
import { ToastProvider } from '../components/Toast'
import { TooltipProvider } from '../ui/Tooltip'
import { ProviderRow } from './ProviderRow'

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

function renderRow(provider: Provider, { index = 0, position = 0, total = 2 } = {}) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter>
            <table>
              <tbody>
                <ProviderRow provider={provider} index={index} position={position} total={total} onEdit={() => {}} onVerify={() => {}} onMove={() => {}} />
              </tbody>
            </table>
          </MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

describe('ProviderRow', () => {
  it('numera a posição na cadeia e destaca o primeiro', () => {
    renderRow(base)
    expect(screen.getByText('1º')).toBeInTheDocument()

    renderRow({ ...base, id: 'p2', name: 'Bedrock' }, { index: 2, position: 2, total: 3 })
    expect(screen.getByText('3º')).toBeInTheDocument()
  })

  it('quem não está pronto não recebe posição e diz o que falta', () => {
    renderRow({ ...base, ready: false, enabled: false, has_credentials: false, credential_keys: [] }, { index: -1 })
    expect(screen.queryByText('1º')).not.toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText(/sem credenciais/)).toBeInTheDocument()
  })

  it('sem modelo padrão, o interruptor fica travado', () => {
    renderRow({ ...base, default_model: null, ready: false })
    expect(screen.getByRole('switch', { name: 'Ativar OpenRouter principal' })).toBeDisabled()
    expect(screen.getByText('nenhum')).toBeInTheDocument()
  })

  it('a seta de subir morre no topo e a de descer no fim', () => {
    renderRow(base, { position: 0, total: 2 })
    expect(screen.getByRole('button', { name: 'Subir OpenRouter principal na cadeia' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Descer OpenRouter principal na cadeia' })).toBeEnabled()
  })

  it('mostra o erro do último teste de quem está fora da cadeia', () => {
    renderRow({ ...base, ready: false, last_status: 'error', last_error: 'Chave recusada pelo provedor.' })
    expect(screen.getByText('Chave recusada pelo provedor.')).toBeInTheDocument()
    expect(screen.getByText('falhou')).toBeInTheDocument()
  })

  it('pausado por limite de uso aparece como tal, não como erro', () => {
    renderRow({ ...base, paused_until: '2026-11-24T10:05:00Z' })
    expect(screen.getByText('pausado')).toBeInTheDocument()
  })

  it('as ações ficam no menu da linha, e testar trava sem credencial', async () => {
    renderRow({ ...base, has_credentials: false, credential_keys: [], ready: false }, { index: -1 })
    await userEvent.click(screen.getByRole('button', { name: 'Ações de OpenRouter principal' }))
    expect(screen.getByRole('menuitem', { name: 'Editar credenciais' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Verificar em etapas' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Remover' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Testar agora' })).toHaveAttribute('aria-disabled', 'true')
  })

  it('abre os modelos numa linha de detalhe, sem sair da tabela', async () => {
    renderRow(base)
    const toggle = screen.getByRole('button', { name: 'Ver os modelos de OpenRouter principal' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(toggle)
    expect(screen.getByRole('button', { name: 'Esconder os modelos de OpenRouter principal' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Modelos cadastrados')).toBeInTheDocument()
  })
})
