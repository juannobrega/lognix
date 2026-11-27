import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, api } from '../api/client'
import type { UpdateInfo } from '../api/types'
import { Alert } from '../components/Alert'
import { CopyButton } from '../components/CopyButton'
import { dateTime } from '../components/format'
import { useToast } from '../components/useToast'
import styles from './UpdateCard.module.css'
import { SelfUpdate } from './SelfUpdate'
import { Switch } from '../ui/Switch'

/**
 * Verificação de atualização, desligada por padrão. Ver ADR 018.
 *
 * O cartão existe mesmo com a verificação desligada, porque é onde se descobre que ela existe —
 * e mostra a versão rodando e o comando de atualizar de qualquer jeito.
 */
export function UpdateCard() {
  const qc = useQueryClient()
  const toast = useToast()
  const info = useQuery({ queryKey: ['update'], queryFn: () => api<UpdateInfo>('/system/update') })

  const ligar = useMutation({
    mutationFn: (enabled: boolean) => api<UpdateInfo>('/system/update', { method: 'PUT', json: { enabled } }),
    onSuccess: (r) => {
      toast.show(r.enabled ? 'Verificação de atualização ligada.' : 'Verificação desligada.', 'success')
      void qc.invalidateQueries({ queryKey: ['update'] })
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao mudar a verificação.', 'error'),
  })

  const d = info.data

  return (
    <section className="card">
      <div className="card-header">
        <h2>Atualização</h2>
        <span className={styles.toggle}>
          <span className="muted">{d?.enabled ? 'verificando' : 'não verifica'}</span>
          <Switch
            checked={d?.enabled ?? false}
            disabled={!d || d.managed}
            pending={ligar.isPending}
            onCheckedChange={(v) => ligar.mutate(v)}
            aria-label="Verificar atualizações"
          />
        </span>
      </div>
      <div className="card-body">
        {d?.outdated && d.available && (
          <Alert
            kind="info"
            message={`A versão ${d.available} está publicada, e esta instalação roda a ${d.current}.`}
            action={
              <a href={d.changelog_url} target="_blank" rel="noreferrer">
                o que mudou
              </a>
            }
          />
        )}
        {d?.managed && (
          <Alert
            kind="info"
            message="updates.check_enabled está declarado no config.yaml. Para mudar pela tela, tire a chave do arquivo."
          />
        )}

        <p className={styles.note}>
          {d?.enabled
            ? 'O Lognix consulta o registro de imagens a cada seis horas para saber se saiu versão nova. Nada é enviado: a consulta só pergunta quais versões existem.'
            : 'Desligada, esta instalação não faz nenhuma chamada para fora. Ligue para o Lognix avisar quando sair versão nova.'}
        </p>

        {d?.enabled && (
          <dl className="kv">
            <dt>Versão publicada</dt>
            <dd className="mono">{d.available ? `v${d.available}` : '— registro não respondeu'}</dd>
            <dt>Verificado em</dt>
            <dd>{d.checked_at ? dateTime(d.checked_at) : '—'}</dd>
          </dl>
        )}

        <p className={styles.note}>Atualizar é trocar a imagem e subir de novo:</p>
        <div className={styles.snippet}>
          <code>{d?.command ?? 'docker compose pull && docker compose up -d'}</code>
          <CopyButton value={d?.command ?? 'docker compose pull && docker compose up -d'} />
        </div>
        <p className={styles.note}>
          Subir uma versão nova roda as migrações de banco pendentes. Tenha um backup recente do Postgres antes —
          especialmente se estiver pulando várias versões.
        </p>

        {d && <SelfUpdate info={d} />}
      </div>
    </section>
  )
}
