import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { User } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import { useToast } from '../components/useToast'

export function UsersPage() {
  const qc = useQueryClient()
  const { user: me } = useAuth()
  const toast = useToast()
  const users = useQuery({ queryKey: ['users'], queryFn: () => api<User[]>('/users') })
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () => api<User>('/users', { method: 'POST', json: { name, email, password } }),
    onSuccess: () => {
      setName('')
      setEmail('')
      setPassword('')
      setError(null)
      toast.show('Usuário criado.', 'success')
      void qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : 'Falha ao criar usuário.'),
  })

  const remove = useMutation({
    mutationFn: (id: string) => api(`/users/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.show('Usuário removido.', 'success')
      void qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : 'Falha ao remover usuário.'),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    create.mutate()
  }

  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-header">
          <h2>Usuários</h2>
        </div>
        {error && (
          <div style={{ padding: 'var(--space-4) var(--space-5) 0' }}>
            <Alert kind="error" message={error} />
          </div>
        )}
        <table className="table">
          <thead>
            <tr>
              <th>Nome</th>
              <th>E-mail</th>
              <th>Criado em</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.data?.map((u) => (
              <tr key={u.id}>
                <td style={{ fontWeight: 500 }}>{u.name}</td>
                <td className="muted">{u.email}</td>
                <td className="muted">{new Date(u.created_at).toLocaleDateString('pt-BR')}</td>
                <td className="right">
                  {u.id !== me?.id && (
                    <Button variant="danger" size="sm" onClick={() => remove.mutate(u.id)} loading={remove.isPending}>
                      Remover
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <div className="card-header">
          <h2>Novo usuário</h2>
        </div>
        <form onSubmit={onSubmit} className="card-body">
          <Field label="Nome" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
          <Field label="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Field
            label="Senha inicial"
            type="password"
            minLength={10}
            help="Mínimo de 10 caracteres."
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Button type="submit" variant="primary" loading={create.isPending}>
            Criar usuário
          </Button>
        </form>
      </div>
    </div>
  )
}
