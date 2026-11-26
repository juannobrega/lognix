import styles from './charts.module.css'

export interface Fatia {
  rotulo: string
  valor: number
  cor?: string
}

/**
 * Barras horizontais para comparar poucas categorias.
 *
 * Preferidas à rosca: comparar comprimento é mais fácil que comparar ângulo, e o rótulo cabe ao
 * lado em vez de exigir uma legenda à parte.
 */
export function BarList({
  itens,
  formata = String,
  vazio = 'Nada no período.',
}: {
  itens: Fatia[]
  formata?: (v: number) => string
  vazio?: string
}) {
  const total = itens.reduce((a, i) => a + i.valor, 0)
  if (total === 0) return <p className={styles.vazio}>{vazio}</p>
  const max = Math.max(...itens.map((i) => i.valor))

  return (
    <ul className={styles.barras}>
      {itens.map((i) => (
        <li key={i.rotulo}>
          <span className={styles.barraRotulo}>{i.rotulo}</span>
          <span className={styles.trilho}>
            <span
              className={styles.barra}
              style={{ width: `${Math.max(2, (i.valor / max) * 100)}%`, background: i.cor ?? 'var(--accent)' }}
            />
          </span>
          <span className={styles.barraValor}>{formata(i.valor)}</span>
        </li>
      ))}
    </ul>
  )
}
