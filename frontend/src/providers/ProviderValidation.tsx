import * as Dialog from '@radix-ui/react-dialog'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { ApiError, api } from '../api/client'
import type { Provider, ValidationStep } from '../api/types'
import { Button } from '../components/Button'
import { ValidationSteps } from '../components/ValidationSteps'
import dialog from '../ui/Dialog.module.css'
import { ProviderIcon } from './icons'
import { PROVIDER_TINT } from './kinds'
import styles from './ProviderValidation.module.css'

interface Resultado {
  ok: boolean
  steps: ValidationStep[]
}

/** Enquanto a resposta não chega, as etapas aparecem como vão ser — a primeira correndo. */
const ESPERANDO: ValidationStep[] = [
  'Credenciais',
  'Serviço alcançável',
  'Modelo disponível',
  'Chamada de teste',
  'Preço para estimar custo',
].map((name, i) => ({ number: i + 1, name, status: i === 0 ? 'running' : 'pending' }))

interface Props {
  provider: Provider | null
  onOpenChange: (open: boolean) => void
  onEditar: () => void
}

/**
 * Valida o provedor em etapas, logo depois de cadastrar.
 *
 * Cadastrar e descobrir dias depois que a credencial estava errada é o pior jeito de usar isto.
 * E "falhou" sozinho não ajuda: credencial recusada, modelo inexistente, serviço fora e preço
 * ausente são quatro problemas com quatro soluções diferentes, e a etapa que para diz qual é.
 */
export function ProviderValidation({ provider, onOpenChange, onEditar }: Props) {
  const qc = useQueryClient()
  const consulta = useQuery({
    queryKey: ['providers', provider?.id, 'validate'],
    queryFn: () => api<Resultado>(`/settings/ai/providers/${provider!.id}/validate`, { method: 'POST' }),
    enabled: provider !== null,
    retry: false,
    gcTime: 0,
    staleTime: 0,
  })

  // A validação faz uma chamada de teste, que muda o estado do provedor e entra em Consumo.
  useEffect(() => {
    if (!consulta.data) return
    void qc.invalidateQueries({ queryKey: ['providers'] })
    void qc.invalidateQueries({ queryKey: ['settings', 'ai'] })
    void qc.invalidateQueries({ queryKey: ['usage'] })
  }, [consulta.data, qc])

  const steps = consulta.data?.steps ?? ESPERANDO
  const falhou = steps.find((s) => s.status === 'failed')
  const pronto = consulta.data?.ok === true && !falhou

  return (
    <Dialog.Root open={provider !== null} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className={dialog.overlay} />
        <Dialog.Content className={dialog.content} style={{ maxWidth: 560 }}>
          <Dialog.Title className={dialog.title}>
            <span className={styles.cabecalho}>
              {provider && (
                <span className={styles.glifo} style={{ ['--tint' as string]: PROVIDER_TINT[provider.kind] }}>
                  <ProviderIcon kind={provider.kind} width={20} height={20} />
                </span>
              )}
              Verificando {provider?.name}
            </span>
          </Dialog.Title>

          <ValidationSteps steps={steps} />

          {consulta.isError && (
            <p className={styles.erro}>
              {consulta.error instanceof ApiError
                ? [consulta.error.message, consulta.error.action].filter(Boolean).join(' ')
                : 'Não foi possível rodar a verificação.'}
            </p>
          )}
          {pronto && (
            <p className={styles.ok}>
              Tudo certo. Ative o provedor para ele entrar na cadeia de fallback.
            </p>
          )}
          {falhou && (
            <p className={styles.erro}>
              A etapa {falhou.number} parou aqui. O provedor fica cadastrado: corrija e verifique de novo.
            </p>
          )}

          <div className={dialog.actions}>
            {falhou && (
              <Button
                onClick={() => {
                  onOpenChange(false)
                  onEditar()
                }}
              >
                Editar credenciais
              </Button>
            )}
            <Button onClick={() => void consulta.refetch()} loading={consulta.isFetching}>
              Verificar de novo
            </Button>
            <Dialog.Close asChild>
              <Button variant="primary">Fechar</Button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
