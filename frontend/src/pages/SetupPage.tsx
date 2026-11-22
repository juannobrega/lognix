import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import styles from './AuthPage.module.css'

export function SetupPage() {
  const { setup, user } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<{ needs_setup: boolean }>('/setup/status', { retry: false })
      .then((s) => !s.needs_setup && navigate('/login', { replace: true }))
      .catch(() => undefined)
  }, [navigate])

  useEffect(() => {
    if (user) navigate('/', { replace: true })
  }, [user, navigate])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await setup(email, name, password)
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'network', 'Não foi possível conectar ao servidor.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={styles.wrap}>
      <form className={styles.card} onSubmit={onSubmit} aria-labelledby="setup-title">
        <div className={styles.brand} id="setup-title">
          <img src="/logo.png" alt="Lognix" className={styles.logoImg} />
          <span>Bem-vindo ao Lognix</span>
        </div>
        <p className={styles.sub}>Crie o primeiro usuário. Ele poderá cadastrar os demais.</p>
        {error && <Alert kind="error" message={error.message} action={error.action} />}
        <Field label="Nome" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
        <Field label="E-mail" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <Field
          label="Senha"
          type="password"
          autoComplete="new-password"
          help="Mínimo de 10 caracteres."
          minLength={10}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Button type="submit" variant="primary" loading={busy}>
          Criar usuário e entrar
        </Button>
      </form>
    </div>
  )
}
