import { useState } from 'react'
import { Button } from './Button'

/**
 * Copia um texto curto. Cai para a seleção manual quando `navigator.clipboard` não existe —
 * é o caso de qualquer acesso por http em IP de rede local, que não é contexto seguro.
 */
export function CopyButton({
  value,
  label = 'Copiar',
  size = 'sm',
}: {
  value: string
  label?: string
  size?: 'md' | 'sm'
}) {
  const [copiado, setCopiado] = useState(false)
  const [falhou, setFalhou] = useState(false)

  async function copiar() {
    try {
      await navigator.clipboard.writeText(value)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 1500)
    } catch {
      setFalhou(true)
    }
  }

  return (
    <Button
      type="button"
      size={size}
      onClick={() => void copiar()}
      title={falhou ? 'Selecione o texto e copie à mão.' : undefined}
    >
      {falhou ? 'copie à mão' : copiado ? 'copiado' : label}
    </Button>
  )
}
