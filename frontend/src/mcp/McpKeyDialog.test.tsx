import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { McpInfo } from '../api/types'
import { ToastProvider } from '../components/Toast'
import { McpKeyDialog } from './McpKeyDialog'

const info: McpInfo = {
  enabled: true,
  has_keys: false,
  managed: false,
  url: 'http://localhost:8080/mcp',
  public_url: 'http://localhost:8080',
  host_allowed: true,
  scopes: [
    {
      nome: 'leitura',
      rotulo: 'Leitura',
      descricao: 'Hosts, projetos e logs.',
      risco: 'Lê os logs dos seus projetos.',
    },
    { nome: 'analise', rotulo: 'Análise', descricao: 'Dispara análise.', risco: 'Gasta dinheiro com o provedor.' },
    { nome: 'admin', rotulo: 'Administração', descricao: 'Consumo e estado.', risco: 'Expõe custos.' },
  ],
  tools: [{ nome: 'lognix_listar_hosts', escopo: 'leitura', descricao: 'Máquinas.' }],
}

const SEGREDO = 'lgxmcp_abcdefghijklmnop'

function montar() {
  const onOpenChange = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <McpKeyDialog info={info} open onOpenChange={onOpenChange} />
      </ToastProvider>
    </QueryClientProvider>,
  )
  return onOpenChange
}

afterEach(() => vi.unstubAllGlobals())

describe('McpKeyDialog', () => {
  it('mostra o risco de vazamento de cada escopo, que é o que decide a escolha', () => {
    montar()
    expect(screen.getByText('Gasta dinheiro com o provedor.')).toBeInTheDocument()
    expect(screen.getByText('Expõe custos.')).toBeInTheDocument()
  })

  it('não deixa criar chave sem nenhuma permissão', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(screen.getByRole('checkbox', { name: /Leitura/ }))
    expect(screen.getByRole('button', { name: 'Criar chave' })).toBeDisabled()
  })

  it('manda os escopos marcados e mostra o segredo sem fechar o diálogo', async () => {
    const user = userEvent.setup()
    const chamadas = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        id: 'k1',
        name: 'Notebook',
        prefix: 'lgxmcp_abcdef',
        scopes: ['analise', 'leitura'],
        enabled: true,
        expires_at: null,
        last_used_at: null,
        calls: 0,
        created_at: '2026-11-27T10:00:00Z',
        secret: SEGREDO,
      }),
    } as Response)
    vi.stubGlobal('fetch', chamadas)
    const onOpenChange = montar()

    await user.type(screen.getByLabelText('Nome'), 'Notebook')
    await user.click(screen.getByRole('checkbox', { name: /Análise/ }))
    await user.click(screen.getByRole('button', { name: 'Criar chave' }))

    expect(await screen.findByText(SEGREDO)).toBeInTheDocument()
    const corpo = JSON.parse(String(chamadas.mock.calls[0][1].body))
    expect(corpo).toMatchObject({ name: 'Notebook', scopes: ['leitura', 'analise'], expires_in_days: null })
    // A chave só existe aqui: fechar sozinho significaria perdê-la.
    expect(screen.getByText(/só tem o hash dela/)).toBeInTheDocument()
    expect(onOpenChange).not.toHaveBeenCalled()
  })
})
