import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import styles from './AuthPage.module.css'

export function LoginPage() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation() as { state?: { from?: { pathname: string } } }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    // Sistema vazio: manda para o cadastro do primeiro usuário.
    api<{ needs_setup: boolean }>('/setup/status', { retry: false })
      .then((s) => s.needs_setup && navigate('/setup', { replace: true }))
      .catch(() => undefined)
  }, [navigate])

  useEffect(() => {
    if (user) navigate(location.state?.from?.pathname ?? '/', { replace: true })
  }, [user, navigate, location.state])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', 'Não foi possível conectar ao servidor.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={styles.wrap}>
      <form className={styles.card} onSubmit={onSubmit} aria-labelledby="login-title">
        <div className={styles.well}>
          <div className={styles.brand} id="login-title">
            <span role="img" aria-label="Lognix" className={styles.logoImg} />
          </div>
          <p className={styles.sub}>Entre para continuar.</p>
          {error && <Alert kind="error" message={error.message} action={error.action} />}
          <Field label="E-mail" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Field
            label="Senha"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Button type="submit" variant="primary" loading={busy}>
            Entrar
          </Button>
        </div>
      </form>
    </div>
  )
}
