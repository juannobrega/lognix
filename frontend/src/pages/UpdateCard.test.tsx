import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
  self_update_enabled: false,
  self_update_managed: false,
  can_self_update: false,
  blocker: null,
  last_attempt: null,
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

describe('UpdateCard › atualizar pela interface', () => {
  it('desligado, não mostra botão nenhum', async () => {
    montar({ self_update_enabled: false, can_self_update: false, blocker: null })
    expect(await screen.findByLabelText('Atualizar pela interface')).not.toBeChecked()
    expect(screen.queryByRole('button', { name: /Atualizar para/ })).not.toBeInTheDocument()
  })

  it('ligado sem socket, explica o que falta em vez de mostrar botão', async () => {
    montar({ self_update_enabled: true, can_self_update: false, blocker: 'socket_ausente' })
    expect(await screen.findByText(/socket do Docker não está montado/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Atualizar para/ })).not.toBeInTheDocument()
  })

  it('socket montado sem permissão tem frase própria, porque o conserto é outro', async () => {
    montar({ self_update_enabled: true, can_self_update: false, blocker: 'sem_permissao' })
    expect(await screen.findByText(/group_add com o grupo docker/)).toBeInTheDocument()
  })

  it('com tudo no lugar, o botão aparece com a versão alvo', async () => {
    montar({ self_update_enabled: true, can_self_update: true })
    expect(await screen.findByRole('button', { name: 'Atualizar para 1.4.0' })).toBeInTheDocument()
  })

  it('a confirmação só libera depois de assumir o backup', async () => {
    const user = userEvent.setup()
    montar({ self_update_enabled: true, can_self_update: true })
    await user.click(await screen.findByRole('button', { name: 'Atualizar para 1.4.0' }))
    // O aviso aparece duas vezes: no cartão e, com mais peso, dentro da confirmação.
    expect(await screen.findByText(/a volta para a versão anterior encontra um banco/)).toBeInTheDocument()
    // Sem marcar o backup, o botão de confirmar nem se chama "atualizar".
    expect(screen.getByRole('button', { name: 'Marque o backup acima' })).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: /backup recente/ }))
    expect(screen.getByRole('button', { name: 'Atualizar agora' })).toBeInTheDocument()
  })

  it('conta como terminou a última tentativa', async () => {
    montar({
      self_update_enabled: true,
      can_self_update: true,
      last_attempt: { state: 'exited', exit_code: 1, finished_at: null, log: 'o novo não subiu' },
    })
    expect(await screen.findByText(/Última tentativa de atualização: falhou/)).toBeInTheDocument()
    expect(screen.getByText('o novo não subiu')).toBeInTheDocument()
  })
})
