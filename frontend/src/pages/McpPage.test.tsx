import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../components/Toast'
import { TooltipProvider } from '../ui/Tooltip'
import { McpPage } from './McpPage'

const INFO = {
  enabled: true,
  has_keys: true,
  managed: false,
  url: 'http://localhost:8080/mcp',
  scopes: [{ nome: 'leitura', rotulo: 'Leitura', descricao: 'Logs.', risco: 'Lê os logs.' }],
  tools: [{ nome: 'lognix_buscar_logs', escopo: 'leitura', descricao: 'Linhas de log de um projeto.' }],
}

const CHAVES = [
  {
    id: 'k1',
    name: 'Notebook',
    prefix: 'lgxmcp_abcdef',
    scopes: ['leitura'],
    enabled: true,
    expires_at: null,
    last_used_at: null,
    calls: 0,
    created_at: '2026-11-27T10:00:00Z',
    secret: null,
  },
  {
    id: 'k2',
    name: 'Desligada',
    prefix: 'lgxmcp_zzzzzz',
    scopes: ['admin'],
    enabled: false,
    expires_at: null,
    last_used_at: '2026-11-26T10:00:00Z',
    calls: 12,
    created_at: '2026-11-20T10:00:00Z',
    secret: null,
  },
]

const CHAMADAS = [
  {
    id: 'c1',
    key_name: 'Notebook',
    tool: 'lognix_buscar_logs',
    ok: false,
    error: "Esta chave não tem o escopo 'admin'.",
    duration_ms: 7,
    created_at: '2026-11-27T10:05:00Z',
  },
]

function montar(info: Record<string, unknown> = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const corpo = url.includes('/calls') ? CHAMADAS : url.includes('/keys') ? CHAVES : { ...INFO, ...info }
      return { ok: true, status: 200, json: async () => corpo } as Response
    }),
  )
}

function Tela() {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <TooltipProvider>
          <MemoryRouter>
            <McpPage />
          </MemoryRouter>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('McpPage', () => {
  it('mostra o endereço e o comando pronto do cliente', async () => {
    montar()
    render(<Tela />)
    expect(await screen.findByText('http://localhost:8080/mcp')).toBeInTheDocument()
    // O comando pronto é o que tira a pessoa daqui com o cliente funcionando.
    expect(screen.getByText(/claude mcp add --transport http lognix/)).toBeInTheDocument()
  })

  it('distingue chave nunca usada de chave desativada', async () => {
    montar()
    render(<Tela />)
    expect(await screen.findByText('Desligada')).toBeInTheDocument()
    expect(screen.getByText('nunca usada')).toBeInTheDocument()
    expect(screen.getByText('desativada')).toBeInTheDocument()
    expect(screen.getByText('lgxmcp_abcdef…')).toBeInTheDocument()
  })

  it('desligado, avisa que o endereço recusa todo mundo e que as chaves ficam', async () => {
    montar({ enabled: false })
    render(<Tela />)
    expect(await screen.findByText(/responde 503 a todo mundo/)).toBeInTheDocument()
    expect(screen.getByLabelText('Servidor MCP')).not.toBeChecked()
  })

  it('ligado e sem chave ativa, diz que ninguém consegue conectar', async () => {
    montar({ has_keys: false })
    render(<Tela />)
    expect(await screen.findByText(/sem nenhuma chave ativa/)).toBeInTheDocument()
  })

  it('declarado no config.yaml, o interruptor não se mexe pela tela', async () => {
    montar({ managed: true })
    render(<Tela />)
    expect(await screen.findByText(/está declarado no config.yaml/)).toBeInTheDocument()
    expect(screen.getByLabelText('Servidor MCP')).toBeDisabled()
  })

  it('lista as ferramentas e o erro da última chamada', async () => {
    montar()
    render(<Tela />)
    // Duas vezes: uma no catálogo de ferramentas, outra na chamada que a usou.
    expect(await screen.findAllByText('lognix_buscar_logs')).toHaveLength(2)
    expect(screen.getByText('Linhas de log de um projeto.')).toBeInTheDocument()
    expect(screen.getByText("Esta chave não tem o escopo 'admin'.")).toBeInTheDocument()
  })
})
