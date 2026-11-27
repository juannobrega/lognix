import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider } from '../components/Toast'
import { EmailPage } from './EmailPage'

const PRESETS = [
  { id: 'gmail', label: 'Gmail / Google Workspace', host: 'smtp.gmail.com', port: 587, security: 'starttls', hint: 'Exige uma senha de app.', username: '' },
  { id: 'sendgrid', label: 'SendGrid', host: 'smtp.sendgrid.net', port: 587, security: 'starttls', hint: '', username: 'apikey' },
  { id: 'custom', label: 'Servidor próprio', host: '', port: 25, security: 'none', hint: '', username: '' },
]

const BASE = {
  enabled: false,
  provider: '',
  host: '',
  port: 587,
  security: 'starttls',
  username: '',
  has_password: false,
  sender: '',
  recipients: '',
  min_severity: 'high',
  projects: '',
  on_host_down: true,
  managed: [] as string[],
  presets: PRESETS,
}

function montar(extras: Record<string, unknown> = {}) {
  const chamadas: Array<[string, unknown]> = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push([url, init?.body ? JSON.parse(String(init.body)) : null])
      return { ok: true, status: 200, json: async () => ({ ...BASE, ...extras }) } as Response
    }),
  )
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <EmailPage />
      </ToastProvider>
    </QueryClientProvider>,
  )
  return chamadas
}

afterEach(() => vi.unstubAllGlobals())

describe('EmailPage', () => {
  it('diz que a mensagem não leva linha de log', async () => {
    montar()
    expect(await screen.findByText(/não leva linha de log/)).toBeInTheDocument()
  })

  it('escolher o provedor preenche servidor, porta e usuário', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByLabelText('Provedor de e-mail'))
    await user.click(screen.getByRole('option', { name: 'SendGrid' }))
    // O usuário do SendGrid é literalmente "apikey", e errar isso parece senha errada.
    expect(screen.getByLabelText('Servidor')).toHaveValue('smtp.sendgrid.net')
    expect(screen.getByLabelText('Usuário')).toHaveValue('apikey')
  })

  it('o preset preenche mas não trava: dá para editar o host', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByLabelText('Provedor de e-mail'))
    await user.click(screen.getByRole('option', { name: 'Gmail / Google Workspace' }))
    const host = screen.getByLabelText('Servidor')
    await user.clear(host)
    await user.type(host, 'relay.interno')
    expect(host).toHaveValue('relay.interno')
  })

  it('mostra a dica do provedor, que é o que o site dele esconde', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByLabelText('Provedor de e-mail'))
    await user.click(screen.getByRole('option', { name: 'Gmail / Google Workspace' }))
    expect(screen.getByText('Exige uma senha de app.')).toBeInTheDocument()
  })

  it('com senha guardada, o campo avisa que em branco mantém a atual', async () => {
    montar({ has_password: true })
    expect(await screen.findByText('Em branco mantém a atual.')).toBeInTheDocument()
  })

  it('campo vindo do config.yaml não se edita na tela', async () => {
    montar({ managed: ['smtp.host', 'smtp.password'] })
    expect(await screen.findByText(/vêm do config.yaml/)).toBeInTheDocument()
    expect(screen.getByLabelText('Servidor')).toBeDisabled()
    expect(screen.getByLabelText('Senha')).toBeDisabled()
  })

  it('salvar manda a porta como número, não como texto', async () => {
    const user = userEvent.setup()
    const chamadas = montar()
    await user.click(await screen.findByRole('button', { name: 'Salvar' }))
    // O campo é um input, então o valor sai string de lá; a API recusaria.
    const corpo = chamadas.at(-1)?.[1] as { port: unknown }
    expect(typeof corpo.port).toBe('number')
  })

  it('explica que só insight novo vira e-mail', async () => {
    montar()
    expect(await screen.findByText(/Recorrência atualiza a contagem/)).toBeInTheDocument()
  })
})
