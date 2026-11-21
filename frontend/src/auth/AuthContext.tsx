import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { AuthContext } from './context'
import { api, session } from '../api/client'
import type { TokenOut, User } from '../api/types'



export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const applySession = useCallback((data: TokenOut) => {
    session.setAccessToken(data.access_token)
    setUser(data.user)
  }, [])

  useEffect(() => {
    session.onLost(() => setUser(null))
    // Tenta retomar a sessão pelo cookie de refresh.
    ;(async () => {
      try {
        const res = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' })
        if (res.ok) applySession((await res.json()) as TokenOut)
      } catch {
        /* sem sessão */
      } finally {
        setLoading(false)
      }
    })()
    return () => session.onLost(null)
  }, [applySession])

  const login = useCallback(
    async (email: string, password: string) => {
      applySession(await api<TokenOut>('/auth/login', { method: 'POST', json: { email, password } }))
    },
    [applySession],
  )

  const setup = useCallback(
    async (email: string, name: string, password: string) => {
      applySession(await api<TokenOut>('/setup', { method: 'POST', json: { email, name, password } }))
    },
    [applySession],
  )

  const logout = useCallback(async () => {
    try {
      await api('/auth/logout', { method: 'POST', retry: false })
    } finally {
      session.setAccessToken(null)
      setUser(null)
    }
  }, [])

  const value = useMemo(() => ({ user, loading, login, setup, logout }), [user, loading, login, setup, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
