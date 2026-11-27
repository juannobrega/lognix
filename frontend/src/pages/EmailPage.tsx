import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { EmailIntegration, SmtpPreset } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { Field } from '../components/Field'
import { SkeletonRows } from '../components/Skeleton'
import { useToast } from '../components/useToast'
import { Select } from '../ui/Select'
import { Switch } from '../ui/Switch'
import styles from './EmailPage.module.css'

const SEVERIDADES = [
  { value: 'critical', label: 'Só crítico' },
  { value: 'high', label: 'Crítico e alto' },
  { value: 'medium', label: 'Crítico, alto e médio' },
  { value: 'low', label: 'Tudo, menos informativo' },
  { value: 'info', label: 'Tudo' },
]

const SEGURANCAS = [
  { value: 'starttls', label: 'STARTTLS (porta 587)' },
  { value: 'tls', label: 'TLS direto (porta 465)' },
  { value: 'none', label: 'Sem criptografia' },
]

interface Rascunho {
  provider: string
  host: string
  port: string
  security: string
  username: string
  password: string
  sender: string
  recipients: string
}

function doServidor(d: EmailIntegration): Rascunho {
  return {
    provider: d.provider || 'custom',
    host: d.host,
    port: String(d.port),
    security: d.security,
    username: d.username,
    password: '',
    sender: d.sender,
    recipients: d.recipients,
  }
}

export function EmailPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const info = useQuery({ queryKey: ['integrations', 'email'], queryFn: () => api<EmailIntegration>('/integrations/email') })
  const [form, setForm] = useState<Rascunho | null>(null)
  const d = info.data

  // O rascunho nasce do servidor uma vez; depois é da pessoa, e salvar é explícito.
  useEffect(() => {
    if (d && form === null) setForm(doServidor(d))
  }, [d, form])

  const salvar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) =>
      api<EmailIntegration>('/integrations/email', { method: 'PUT', json: corpo }),
    onSuccess: (r) => {
      qc.setQueryData(['integrations', 'email'], r)
      setForm(doServidor(r))
      toast.show('Configuração salva.', 'success')
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao salvar.', 'error'),
  })

  const testar = useMutation({
    mutationFn: () => api<{ ok: boolean; error: string | null }>('/integrations/email/test', { method: 'POST' }),
    onSuccess: (r) =>
      r.ok
        ? toast.show('E-mail de teste enviado. Confira a caixa do destinatário.', 'success')
        : toast.show(r.error ?? 'Não consegui enviar.', 'error'),
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao testar.', 'error'),
  })

  if (!d || !form) return <SkeletonRows rows={6} />

  const preset: SmtpPreset | undefined = d.presets.find((p) => p.id === form.provider)
  const travado = (chave: string) => d.managed.includes(chave)

  function escolherProvedor(id: string) {
    const p = d!.presets.find((x) => x.id === id)
    if (!p) return
    // Preenche, não trava: SES muda de host por região e relay interno não tem preset.
    setForm((f) => ({
      ...f!,
      provider: id,
      host: p.host || f!.host,
      port: String(p.port),
      security: p.security,
      username: p.username || f!.username,
    }))
  }

  return (
    <div className={styles.page}>
      <section className="card">
        <div className="card-header">
          <h2>Avisar por e-mail</h2>
          <span className={styles.toggle}>
            <span className="muted">{d.enabled ? 'ligado' : 'desligado'}</span>
            <Switch
              checked={d.enabled}
              pending={salvar.isPending}
              disabled={travado('smtp.enabled')}
              onCheckedChange={(v) => salvar.mutate({ enabled: v })}
              aria-label="Avisar por e-mail"
            />
          </span>
        </div>
        <div className="card-body">
          {d.managed.length > 0 && (
            <Alert
              kind="info"
              message={`Estes campos vêm do config.yaml e não se editam aqui: ${d.managed.join(', ')}.`}
            />
          )}
          <p className="muted">
            O Lognix detecta um erro crítico às três da manhã e ninguém fica sabendo até alguém abrir a tela. Com o
            e-mail ligado, ele avisa. A mensagem leva título, severidade, projeto e causa provável —{' '}
            <strong>não leva linha de log</strong>, porque caixa de e-mail é cópia que escapa do controle de acesso.
          </p>
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Servidor</h2>
        </div>
        <div className="card-body">
          <div className={styles.campo}>
            <label htmlFor="smtp-provider">Provedor</label>
            <Select
              id="smtp-provider"
              aria-label="Provedor de e-mail"
              value={form.provider}
              options={d.presets.map((p) => ({ value: p.id, label: p.label }))}
              onValueChange={escolherProvedor}
            />
            {preset?.hint && <span className={styles.ajuda}>{preset.hint}</span>}
          </div>

          <div className={styles.dupla}>
            <Field
              label="Servidor"
              value={form.host}
              placeholder="smtp.exemplo.com"
              disabled={travado('smtp.host')}
              onChange={(e) => setForm({ ...form, host: e.target.value })}
            />
            <Field
              label="Porta"
              type="number"
              value={form.port}
              disabled={travado('smtp.port')}
              onChange={(e) => setForm({ ...form, port: e.target.value })}
            />
          </div>

          <div className={styles.campo}>
            <label htmlFor="smtp-security">Segurança</label>
            <Select
              id="smtp-security"
              aria-label="Modo de segurança"
              value={form.security}
              options={SEGURANCAS}
              onValueChange={(v) => setForm({ ...form, security: v })}
            />
          </div>

          <div className={styles.dupla}>
            <Field
              label="Usuário"
              autoComplete="off"
              value={form.username}
              help="Em branco para relay que não pede autenticação."
              disabled={travado('smtp.username')}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
            <Field
              label="Senha"
              type="password"
              autoComplete="new-password"
              value={form.password}
              placeholder={d.has_password ? '•••••••• (uma senha já está salva)' : ''}
              help={d.has_password ? 'Em branco mantém a atual.' : undefined}
              disabled={travado('smtp.password')}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </div>

          <div className={styles.dupla}>
            <Field
              label="Remetente"
              type="email"
              value={form.sender}
              placeholder="lognix@suaempresa.com"
              disabled={travado('smtp.from')}
              onChange={(e) => setForm({ ...form, sender: e.target.value })}
            />
            <Field
              label="Destinatários"
              value={form.recipients}
              placeholder="ops@suaempresa.com, plantao@suaempresa.com"
              help="Separados por vírgula."
              disabled={travado('smtp.to')}
              onChange={(e) => setForm({ ...form, recipients: e.target.value })}
            />
          </div>

          <div className={styles.acoes}>
            <Button
              variant="primary"
              loading={salvar.isPending}
              onClick={() => salvar.mutate({ ...form, port: Number(form.port) })}
            >
              Salvar
            </Button>
            <Button loading={testar.isPending} onClick={() => testar.mutate()}>
              Enviar e-mail de teste
            </Button>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Quando avisar</h2>
        </div>
        <div className="card-body">
          <div className={styles.campo}>
            <label htmlFor="min-sev">Severidade mínima</label>
            <Select
              id="min-sev"
              aria-label="Severidade mínima"
              value={d.min_severity}
              options={SEVERIDADES}
              onValueChange={(v) => salvar.mutate({ min_severity: v })}
            />
          </div>

          <Field
            label="Projetos"
            value={d.projects}
            placeholder="em branco: todos"
            help="Separados por vírgula. Em branco, qualquer projeto avisa."
            disabled={travado('alerts.projects')}
            onChange={(e) => qc.setQueryData(['integrations', 'email'], { ...d, projects: e.target.value })}
            onBlur={(e) => salvar.mutate({ projects: e.target.value })}
          />

          <div className={styles.linha}>
            <span>
              <strong>Host desconectado também avisa</strong>
              <span className={styles.ajuda}>
                Enquanto um host está fora, os containers dele não são coletados nem analisados.
              </span>
            </span>
            <Switch
              checked={d.on_host_down}
              pending={salvar.isPending}
              disabled={travado('alerts.on_host_down')}
              onCheckedChange={(v) => salvar.mutate({ on_host_down: v })}
              aria-label="Avisar quando um host cair"
            />
          </div>

          <p className={styles.ajuda}>
            Só insight <strong>novo</strong> vira e-mail. Recorrência atualiza a contagem do que já existe e não manda
            nada — um erro persistente mandaria uma mensagem por ciclo, e o filtro de quem recebe aprenderia a jogar o
            Lognix no lixo.
          </p>
        </div>
      </section>
    </div>
  )
}
