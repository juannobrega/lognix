/**
 * Minigráfico de barras verticais. É o motivo do símbolo do Lognix aplicado a dados:
 * mostra a forma de uma série curta sem trazer uma biblioteca de gráficos para a página.
 */
export function SparkBars({ values, label }: { values: number[]; label: string }) {
  const max = Math.max(...values, 1)
  return (
    <div className="sparkbars" role="img" aria-label={label}>
      {values.map((v, i) => (
        <i key={i} className={v === 0 ? 'empty' : undefined} style={{ ['--v' as string]: Math.max(v / max, 0.04) }} />
      ))}
    </div>
  )
}
