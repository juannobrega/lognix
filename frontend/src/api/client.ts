/**
 * Cliente HTTP único. Anexa o access token, tenta um refresh em 401, e converte
 * o formato de erro da API em ApiError. Na fase 0.1.0 os tipos são escritos à mão;
 * a geração a partir do OpenAPI entra quando a API crescer.
 */

export class ApiError extends Error {
  code: string
  action?: string
  status: number
  constructor(status: number, code: string, message: string, action?: string) {
    super(message)
    this.status = status
    this.code = code
    this.action = action
  }
}

type Json = Record<string, unknown> | unknown[] | null

let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null
let onSessionLost: (() => void) | null = null

export const session = {
  setAccessToken(token: string | null) {
    accessToken = token
  },
  getAccessToken() {
    return accessToken
  },
  onLost(handler: (() => void) | null) {
    onSessionLost = handler
  },
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { error?: { code: string; message: string; action?: string } }
    if (body?.error) return new ApiError(res.status, body.error.code, body.error.message, body.error.action)
  } catch {
    /* corpo não é JSON */
  }
  return new ApiError(res.status, 'http_error', `Erro HTTP ${res.status}`)
}

async function tryRefresh(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' })
        if (!res.ok) return false
        const data = (await res.json()) as { access_token: string }
        accessToken = data.access_token
        return true
      } catch {
        return false
      } finally {
        refreshing = null
      }
    })()
  }
  return refreshing
}

export async function api<T = Json>(
  path: string,
  init: RequestInit & { json?: unknown; retry?: boolean } = {},
): Promise<T> {
  const { json, retry = true, ...rest } = init
  const headers = new Headers(rest.headers)
  if (json !== undefined) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)

  const res = await fetch(`/api/v1${path}`, {
    ...rest,
    headers,
    credentials: 'include',
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  })

  if (res.status === 401 && retry && !path.startsWith('/auth/login') && !path.startsWith('/setup')) {
    if (await tryRefresh()) return api<T>(path, { ...init, retry: false })
    accessToken = null
    onSessionLost?.()
  }
  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
