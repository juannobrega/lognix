import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { HostCreated, SshAuthMethod } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import { ValidationSteps } from '../components/ValidationSteps'
import { ContainerStateBadge } from '../components/StatusBadge'
import { useValidation } from '../hosts/useValidation'

export function NewHostPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [port, setPort] = useState('22')
  const [user, setUser] = useState('')
  const [method, setMethod] = useState<SshAuthMethod>('key')
  const [privateKey, setPrivateKey] = useState('')
  const [passphrase, setPassphrase] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [created, setCreated] = useState<HostCreated | null>(null)
  const validation = useValidation(created?.validation_id ?? null)

  const create = useMutation({
    mutationFn: () =>
      api<HostCreated>('/hosts', {
        method: 'POST',
        json: {
          name,
          address,
          ssh_port: Number(port),
          ssh_user: user,
          ssh_auth_method: method,
          private_key: method !== 'password' ? privateKey : undefined,
          key_passphrase: method === 'key_passphrase' ? passphrase : undefined,
          password: method === 'password' ? password : undefined,
        },
      }),
    onSuccess: (data) => {
      setCreated(data)
      void qc.invalidateQueries({ queryKey: ['hosts'] })
    },
    onError: (err) => setError(err instanceof ApiError ? err : new ApiError(0, 'network', 'Falha de rede.')),
  })

  const retry = useMutation({
    mutationFn: () => api<{ validation_id: string }>(`/hosts/${created!.host.id}/reconnect`, { method: 'POST' }),
    onSuccess: (data) => setCreated((c) => (c ? { ...c, validation_id: data.validation_id } : c)),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    create.mutate()
  }

  if (created) {
    const v = validation.data
    return (
      <>
        <h1>Conectando a {created.host.name}</h1>
        {v ? <ValidationSteps steps={v.steps} /> : <p>Iniciando validação…</p>}
        {v?.status === 'failed' && (
          <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
            <Button variant="primary" onClick={() => retry.mutate()} loading={retry.isPending}>
              Tentar de novo
            </Button>
            <Link to={`/hosts/${created.host.id}`}>
              <Button>Editar credenciais</Button>
            </Link>
          </div>
        )}
        {v?.status === 'ok' && (
          <>
            <Alert message="Host conectado. Escolha os containers a monitorar na tela do host." />
            <h2>Containers encontrados ({v.containers?.length ?? 0})</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 'var(--space-5)' }}>
              <thead>
                <tr style={{ textAlign: 'left', color: 'var(--fg-muted)' }}>
                  <th>Nome</th>
                  <th>Imagem</th>
                  <th>Estado</th>
                  <th>Compose</th>
                </tr>
              </thead>
              <tbody>
                {v.containers?.map((c) => (
                  <tr key={c.docker_id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td>{c.name}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }}>{c.image}</td>
                    <td>
                      <ContainerStateBadge state={c.state} />
                    </td>
                    <td style={{ color: 'var(--fg-muted)' }}>
                      {c.compose_project ? `${c.compose_project} / ${c.compose_service ?? ''}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Button variant="primary" onClick={() => navigate(`/hosts/${created.host.id}`)}>
              Ir para o host e escolher containers
            </Button>
          </>
        )}
      </>
    )
  }

  return (
    <>
      <h1>Cadastrar host</h1>
      <p style={{ color: 'var(--fg-muted)' }}>
        Uma máquina com Docker acessível por SSH. O usuário SSH precisa ter acesso ao socket do Docker. Nada será instalado nela e nenhum
        comando de alteração será enviado.
      </p>
      {error && <Alert kind="error" message={error.message} action={error.action} />}
      <form onSubmit={onSubmit} style={{ maxWidth: 560 }}>
        <Field label="Nome" help="Identifica o host no Lognix. Letras, números, - e _." value={name} onChange={(e) => setName(e.target.value)} required pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,62}" />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 120px', gap: 'var(--space-3)' }}>
          <Field label="Endereço" help="IP ou DNS" value={address} onChange={(e) => setAddress(e.target.value)} required />
          <Field label="Porta SSH" type="number" min={1} max={65535} value={port} onChange={(e) => setPort(e.target.value)} required />
        </div>
        <Field label="Usuário SSH" value={user} onChange={(e) => setUser(e.target.value)} required autoComplete="off" />
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <label style={{ display: 'block', fontSize: 'var(--text-sm)', fontWeight: 500, marginBottom: 4 }} htmlFor="method">
            Autenticação
          </label>
          <select id="method" value={method} onChange={(e) => setMethod(e.target.value as SshAuthMethod)} style={{ padding: '8px 12px' }}>
            <option value="key">Chave privada (recomendado)</option>
            <option value="key_passphrase">Chave privada com passphrase</option>
            <option value="password">Senha</option>
          </select>
          {method === 'password' && (
            <p style={{ color: 'var(--warn)', fontSize: 'var(--text-sm)' }}>Senha é a opção menos segura. Prefira chave quando possível.</p>
          )}
        </div>
        {method !== 'password' && (
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <label style={{ display: 'block', fontSize: 'var(--text-sm)', fontWeight: 500, marginBottom: 4 }} htmlFor="pk">
              Chave privada
            </label>
            <textarea
              id="pk"
              value={privateKey}
              onChange={(e) => setPrivateKey(e.target.value)}
              rows={8}
              required
              spellCheck={false}
              placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
              style={{ width: '100%', fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', padding: 8, border: '1px solid var(--border)', borderRadius: 4, background: 'var(--bg-elevated)' }}
            />
          </div>
        )}
        {method === 'key_passphrase' && (
          <Field label="Passphrase da chave" type="password" autoComplete="off" value={passphrase} onChange={(e) => setPassphrase(e.target.value)} required />
        )}
        {method === 'password' && (
          <Field label="Senha SSH" type="password" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)} required />
        )}
        <Button type="submit" variant="primary" loading={create.isPending}>
          Conectar
        </Button>
      </form>
    </>
  )
}
