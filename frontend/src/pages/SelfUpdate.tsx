import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { UpdateInfo } from '../api/types'
import { Alert } from '../components/Alert'
import { Button } from '../components/Button'
import { useToast } from '../components/useToast'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { Switch } from '../ui/Switch'
import styles from './UpdateCard.module.css'

/** Cada impedimento tem conserto diferente, então cada um tem frase própria. */
const IMPEDIMENTO: Record<string, string> = {
  socket_ausente:
    'O socket do Docker não está montado no contêiner do Lognix. Sem ele, o Lognix não tem como trocar a própria imagem.',
  sem_permissao:
    'O socket está montado, mas o processo do Lognix não tem permissão para usá-lo. Falta o group_add com o grupo docker do host.',
  container_desconhecido: 'O Docker respondeu, mas não soube dizer qual contêiner é o do Lognix.',
  docker_indisponivel: 'O Docker desta máquina não respondeu.',
}

/**
 * Atualização pela interface. Ver ADR 019.
 *
 * Enquanto o novo contêiner sobe, esta tela morre junto com o antigo. O componente assume isso:
 * depois de confirmar, fica consultando a saúde até a versão responder outra — e quando volta, é
 * o Lognix novo que conta como terminou, lendo os registros do auxiliar.
 */
export function SelfUpdate({ info }: { info: UpdateInfo }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [confirmando, setConfirmando] = useState(false)
  const [trocando, setTrocando] = useState(false)
  const [reconheceu, setReconheceu] = useState(false)

  const ligar = useMutation({
    mutationFn: (self_update_enabled: boolean) =>
      api<UpdateInfo>('/system/update', { method: 'PUT', json: { self_update_enabled } }),
    onSuccess: (r) => {
      toast.show(r.self_update_enabled ? 'Atualização pela interface ligada.' : 'Desligada.', 'success')
      void qc.invalidateQueries({ queryKey: ['update'] })
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao mudar o interruptor.', 'error'),
  })

  const aplicar = useMutation({
    mutationFn: () => api('/system/update/apply', { method: 'POST', json: { version: info.available } }),
    onSuccess: () => {
      setConfirmando(false)
      setTrocando(true)
    },
    onError: (e) => toast.show(e instanceof ApiError ? e.message : 'Falha ao iniciar a atualização.', 'error'),
  })

  // Enquanto troca, o backend some e volta. Recarregar quando ele responder de novo é o que
  // devolve a pessoa a uma tela coerente — a antiga está mostrando dados de outra versão.
  useEffect(() => {
    if (!trocando) return
    let caiu = false
    const timer = setInterval(async () => {
      try {
        const r = await fetch('/api/v1/health')
        if (!r.ok) {
          caiu = true
          return
        }
        if (caiu) window.location.reload()
      } catch {
        caiu = true
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [trocando])

  if (trocando) {
    return (
      <Alert
        kind="info"
        message={`Trocando para a versão ${info.available}. O Lognix vai ficar fora do ar por um minuto e esta página recarrega sozinha quando ele voltar. Se o novo não subir, o anterior volta ao ar automaticamente.`}
      />
    )
  }

  return (
    <>
      <div className={styles.linha}>
        <span>
          <strong>Atualizar pela interface</strong>
          <span className={styles.note}>
            Exige o socket do Docker montado no contêiner — o que dá ao Lognix controle do Docker desta máquina.
          </span>
        </span>
        <Switch
          checked={info.self_update_enabled}
          disabled={info.self_update_managed || ligar.isPending}
          onCheckedChange={(v) => ligar.mutate(v)}
          aria-label="Atualizar pela interface"
        />
      </div>

      {info.self_update_enabled && !info.can_self_update && info.blocker && (
        <Alert kind="warn" message={IMPEDIMENTO[info.blocker] ?? 'Não há acesso ao Docker desta máquina.'} />
      )}

      {info.self_update_enabled && info.can_self_update && info.outdated && info.available && (
        <>
          <Button variant="primary" onClick={() => setConfirmando(true)}>
            Atualizar para {info.available}
          </Button>
          <ConfirmDialog
            open={confirmando}
            onOpenChange={(v) => {
              setConfirmando(v)
              if (!v) setReconheceu(false)
            }}
            title={`Atualizar para ${info.available}?`}
            description={
              <span>
                O Lognix vai sair do ar por cerca de um minuto. Se a versão nova não subir, a anterior volta
                automaticamente.
                <br />
                <br />
                <strong>Subir versão roda as migrações de banco pendentes.</strong> Se uma migração falhar no meio, a
                volta para a versão anterior encontra um banco que já avançou — e a versão anterior pode não entender o
                esquema novo. Isso nenhum rollback conserta.
                <br />
                <br />
                <label className={styles.reconhece}>
                  <input type="checkbox" checked={reconheceu} onChange={(e) => setReconheceu(e.target.checked)} />
                  Tenho um backup recente do Postgres.
                </label>
              </span>
            }
            confirmLabel={reconheceu ? 'Atualizar agora' : 'Marque o backup acima'}
            danger
            loading={aplicar.isPending}
            onConfirm={() => reconheceu && aplicar.mutate()}
          />
        </>
      )}

      {info.last_attempt && (
        <details className={styles.tentativa}>
          <summary>
            Última tentativa de atualização: {info.last_attempt.exit_code === 0 ? 'concluída' : 'falhou'}
          </summary>
          <pre>{info.last_attempt.log || 'sem registros'}</pre>
        </details>
      )}
    </>
  )
}
