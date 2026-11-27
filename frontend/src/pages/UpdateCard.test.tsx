import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../components/Toast'
import { UpdateCard } from './UpdateCard'

const BASE = {
  enabled: true,
  managed: false,
  current: '1.3.0',
  available: '1.4.0',
  outdated: true,
  checked_at: '2026-11-27T15:00:00Z',
  changelog_url: 'https://juannobrega.github.io/lognix/CHANGELOG/',
  command: 'docker compose pull && docker compose up -d',
}

function montar(info: Record<string, unknown> = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ ...BASE, ...info }) }) as Response),
  )
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <UpdateCard />
      </ToastProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('UpdateCard', () => {
  it('avisa da versão nova com link do changelog', async () => {
    montar()
    expect(await screen.findByText(/A versão 1.4.0 está publicada/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'o que mudou' })).toHaveAttribute('href', BASE.changelog_url)
  })

  it('desligada, diz que nada sai, e nem mostra versão publicada', async () => {
    montar({ enabled: false, available: null, outdated: false, checked_at: null })
    expect(await screen.findByText(/não faz nenhuma chamada para fora/)).toBeInTheDocument()
    expect(screen.queryByText('Versão publicada')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Verificar atualizações')).not.toBeChecked()
  })

  it('ligada e sem resposta do registro, não inventa versão', async () => {
    montar({ available: null, outdated: false })
    expect(await screen.findByText(/registro não respondeu/)).toBeInTheDocument()
  })

  it('sempre avisa da migração antes de mandar atualizar', async () => {
    // O comando é um clique; a migração de banco que ele dispara não tem desfazer.
    montar()
    expect(await screen.findByText(/backup recente do Postgres/)).toBeInTheDocument()
  })

  it('declarada no config.yaml, o interruptor não se mexe', async () => {
    montar({ managed: true })
    expect(await screen.findByText(/declarado no config.yaml/)).toBeInTheDocument()
    expect(screen.getByLabelText('Verificar atualizações')).toBeDisabled()
  })
})
