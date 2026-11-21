import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { ApiError, api } from '../api/client'
import type { User } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Field } from '../components/Field'

export function UsersPage() {
  const qc = useQueryClient()
  const { user: me } = useAuth()
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
      void qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : 'Falha ao criar usuário.'),
  })

  const remove = useMutation({
    mutationFn: (id: string) => api(`/users/${id}`, { method: 'DELETE' }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['users'] }),
    onError: (err) => setError(err instanceof ApiError ? err.message : 'Falha ao remover usuário.'),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    create.mutate()
  }

  return (
    <>
      <h1>Usuários</h1>
      {error && <Alert kind="error" message={error} />}
      <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 'var(--space-6)' }}>
        <thead>
          <tr style={{ textAlign: 'left', color: 'var(--fg-muted)' }}>
            <th>Nome</th>
            <th>E-mail</th>
            <th>Criado em</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {users.data?.map((u) => (
            <tr key={u.id} style={{ borderTop: '1px solid var(--border)' }}>
              <td>{u.name}</td>
              <td>{u.email}</td>
              <td>{new Date(u.created_at).toLocaleString('pt-BR')}</td>
              <td style={{ textAlign: 'right' }}>
                {u.id !== me?.id && (
                  <Button variant="danger" onClick={() => remove.mutate(u.id)} loading={remove.isPending}>
                    Remover
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2>Novo usuário</h2>
      <form onSubmit={onSubmit} style={{ maxWidth: 400 }}>
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
          Criar
        </Button>
      </form>
    </>
  )
}
