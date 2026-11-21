export interface User {
  id: string
  email: string
  name: string
  created_at: string
}

export interface TokenOut {
  access_token: string
  token_type: 'bearer'
  expires_at: string
  user: User
}

export interface Health {
  status: 'ok' | 'degraded'
  version: string
  components: Record<string, { ok: boolean; detail?: string | null }>
}
