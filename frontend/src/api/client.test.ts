import { api, session } from './client'

describe('api client', () => {
  beforeEach(() => {
    session.setAccessToken(null)
    vi.restoreAllMocks()
  })

  it('converte erro da API em ApiError com code e action', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'rate_limited', message: 'Muitas tentativas.', action: 'Aguarde.' } }), {
        status: 429,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    await expect(api('/auth/login', { method: 'POST', json: {} })).rejects.toMatchObject({
      code: 'rate_limited',
      action: 'Aguarde.',
      status: 429,
    })
  })

  it('anexa o bearer token e tenta refresh em 401', async () => {
    session.setAccessToken('velho')
    const calls: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      calls.push(url)
      if (url.endsWith('/auth/refresh')) {
        return new Response(JSON.stringify({ access_token: 'novo' }), { status: 200 })
      }
      const auth = new Headers(init?.headers).get('Authorization')
      if (auth === 'Bearer velho') return new Response('', { status: 401 })
      return new Response(JSON.stringify({ ok: true }), { status: 200 })
    })
    await expect(api('/users')).resolves.toEqual({ ok: true })
    expect(calls).toEqual(['/api/v1/users', '/api/v1/auth/refresh', '/api/v1/users'])
    expect(session.getAccessToken()).toBe('novo')
  })
})
