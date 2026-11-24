import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { HostCreated, SshAuthMethod } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import { ValidationSteps } from '../components/ValidationSteps'
import { Select } from '../ui/Select'
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
        <div className="page-header">
          <div>
            <h1>Conectando a {created.host.name}</h1>
            <p className="subtitle">Validação em seis etapas. Cada falha vem com o que fazer.</p>
          </div>
        </div>
        <div className="card card-body" style={{ maxWidth: 720, marginBottom: 'var(--space-5)' }}>
          {v ? <ValidationSteps steps={v.steps} /> : <p>Iniciando validação…</p>}
        </div>
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
            <div className="card" style={{ marginBottom: 'var(--space-5)' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Imagem</th>
                  <th>Estado</th>
                  <th>Compose</th>
                </tr>
              </thead>
              <tbody>
                {v.containers?.map((c) => (
                  <tr key={c.docker_id}>
                    <td style={{ fontWeight: 500 }}>{c.name}</td>
                    <td className="mono">{c.image}</td>
                    <td>
                      <ContainerStateBadge state={c.state} />
                    </td>
                    <td className="muted">{c.compose_project ? `${c.compose_project} / ${c.compose_service ?? ''}` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
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
      <div className="page-header">
        <div>
          <h1>Cadastrar host</h1>
          <p className="subtitle">
            Uma máquina com Docker acessível por SSH. O usuário SSH precisa ter acesso ao socket do Docker. Nada será instalado nela e nenhum
            comando de alteração será enviado.
          </p>
        </div>
      </div>
      {error && <Alert kind="error" message={error.message} action={error.action} />}
      <form onSubmit={onSubmit} className="card card-body" style={{ maxWidth: 600 }}>
        <Field label="Nome" help="Identifica o host no Lognix. Letras, números, - e _." value={name} onChange={(e) => setName(e.target.value)} required pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,62}" />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 120px', gap: 'var(--space-4)' }}>
          <Field label="Endereço" help="IP ou DNS" value={address} onChange={(e) => setAddress(e.target.value)} required />
          <Field label="Porta SSH" type="number" min={1} max={65535} value={port} onChange={(e) => setPort(e.target.value)} required />
        </div>
        <Field label="Usuário SSH" value={user} onChange={(e) => setUser(e.target.value)} required autoComplete="off" />
        <div style={{ marginBottom: 'var(--space-5)' }}>
          <label htmlFor="method">Autenticação</label>
          <Select
            id="method"
            aria-label="Método de autenticação"
            value={method}
            onValueChange={(v) => setMethod(v as SshAuthMethod)}
            minWidth={280}
            options={[
              { value: 'key', label: 'Chave privada (recomendado)' },
              { value: 'key_passphrase', label: 'Chave privada com passphrase' },
              { value: 'password', label: 'Senha' },
            ]}
          />
          {method === 'password' && (
            <p className="muted" style={{ color: 'var(--warn)', fontSize: 'var(--text-sm)', marginBottom: 0 }}>
              Senha é a opção menos segura. Prefira chave quando possível.
            </p>
          )}
        </div>
        {method !== 'password' && (
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <label htmlFor="pk">Chave privada</label>
            <textarea
              id="pk"
              value={privateKey}
              onChange={(e) => setPrivateKey(e.target.value)}
              rows={8}
              required
              spellCheck={false}
              placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
              style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)' }}
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
