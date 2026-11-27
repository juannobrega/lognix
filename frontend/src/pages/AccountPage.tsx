import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import { useToast } from '../components/useToast'

/** Espelha MIN_PASSWORD_LENGTH do backend; divergir aqui só produz erro depois do envio. */
const MIN = 10

/**
 * A própria conta. Por enquanto só a senha, que é o que faltava: o endpoint existia desde o
 * começo e não havia tela — o admin definia a sua senha e você nunca podia trocá-la.
 */
export function AccountPage() {
  const { user, logout } = useAuth()
  const toast = useToast()
  const [atual, setAtual] = useState('')
  const [nova, setNova] = useState('')
  const [repetida, setRepetida] = useState('')

  const trocar = useMutation({
    mutationFn: () =>
      api('/users/me/password', {
        method: 'PUT',
        json: { current_password: atual, new_password: nova },
      }),
    onSuccess: () => {
      // O backend invalida todas as sessões ao trocar a senha, inclusive esta: sair aqui evita
      // que a pessoa continue clicando numa tela que já não tem sessão válida por trás.
      toast.show('Senha alterada. Entre de novo com a senha nova.', 'success')
      void logout()
    },
    onError: (e) =>
      toast.show(
        e instanceof ApiError ? [e.message, e.action].filter(Boolean).join(' ') : 'Falha ao trocar a senha.',
        'error',
      ),
  })

  const curta = nova.length > 0 && nova.length < MIN
  const diferente = repetida.length > 0 && nova !== repetida
  const pode = atual.length > 0 && nova.length >= MIN && nova === repetida && !trocar.isPending

  function enviar(e: FormEvent) {
    e.preventDefault()
    if (pode) trocar.mutate()
  }

  return (
    <div className="stack" style={{ maxWidth: 560 }}>
      <div className="page-header">
        <div>
          <span className="eyebrow">Conta</span>
          <h1>{user?.name}</h1>
          <p className="subtitle">{user?.email}</p>
        </div>
      </div>

      <section className="card">
        <div className="card-header">
          <h2>Trocar a senha</h2>
        </div>
        <form className="card-body" onSubmit={enviar}>
          <Field
            label="Senha atual"
            type="password"
            autoComplete="current-password"
            value={atual}
            onChange={(e) => setAtual(e.target.value)}
            required
          />
          <Field
            label="Nova senha"
            type="password"
            autoComplete="new-password"
            value={nova}
            onChange={(e) => setNova(e.target.value)}
            help={`Pelo menos ${MIN} caracteres.`}
            error={curta ? `A senha precisa ter pelo menos ${MIN} caracteres.` : undefined}
            required
          />
          <Field
            label="Repita a nova senha"
            type="password"
            autoComplete="new-password"
            value={repetida}
            onChange={(e) => setRepetida(e.target.value)}
            error={diferente ? 'As duas não batem.' : undefined}
            required
          />
          <p className="muted" style={{ fontSize: 'var(--text-sm)', marginTop: 0 }}>
            Trocar a senha encerra todas as sessões, inclusive as de outros navegadores. Você
            precisará entrar de novo.
          </p>
          <Button type="submit" variant="primary" disabled={!pode} loading={trocar.isPending}>
            Trocar a senha
          </Button>
        </form>
      </section>
    </div>
  )
}
