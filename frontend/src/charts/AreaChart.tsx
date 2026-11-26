import { useId } from 'react'
import styles from './charts.module.css'

export interface Serie {
  nome: string
  cor: string
  valores: number[]
}

interface Props {
  series: Serie[]
  /** Rótulo de cada ponto. Só alguns são desenhados, senão o eixo vira borrão. */
  rotulos: string[]
  formata?: (v: number) => string
  altura?: number
  'aria-label': string
}

function caminho(valores: number[], max: number, w: number, h: number): string {
  if (valores.length === 0) return ''
  const passo = valores.length > 1 ? w / (valores.length - 1) : w
  return valores
    .map((v, i) => `${i === 0 ? 'M' : 'L'} ${(i * passo).toFixed(1)} ${(h - (v / max) * h).toFixed(1)}`)
    .join(' ')
}

/**
 * Área para séries temporais. Desenho nosso, sem biblioteca de gráficos.
 *
 * Um número diz o tamanho; a linha diz a direção, que é a pergunta de quem abre um painel. O
 * eixo y não é desenhado de propósito: aqui o que importa é a forma e o pico, e uma régua de
 * valores roubaria largura de 24 horas de dados. O pico vai escrito na legenda.
 */
export function AreaChart({ series, rotulos, formata = String, altura = 120, ...aria }: Props) {
  const id = useId()
  const w = 1000
  const h = altura
  const max = Math.max(1, ...series.flatMap((s) => s.valores))
  const n = series[0]?.valores.length ?? 0

  if (n === 0) return <p className={styles.vazio}>Sem dados no período.</p>

  // Quatro marcas bastam para situar; mais que isso vira ruído.
  const marcas = [...new Set([0, Math.floor(n / 3), Math.floor((2 * n) / 3), n - 1])]

  return (
    <figure className={styles.figura}>
      <figcaption className={styles.legenda}>
        {series.map((s) => (
          <span key={s.nome} className={styles.chave}>
            <i style={{ background: s.cor }} aria-hidden="true" />
            {s.nome}
          </span>
        ))}
        <span className={styles.pico}>pico {formata(max)}</span>
      </figcaption>

      <svg viewBox={`0 0 ${w} ${h}`} className={styles.svg} role="img" aria-label={aria['aria-label']} preserveAspectRatio="none">
        <defs>
          {series.map((s, i) => (
            <linearGradient key={s.nome} id={`${id}-${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.cor} stopOpacity="0.3" />
              <stop offset="100%" stopColor={s.cor} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>

        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1="0" x2={w} y1={h * f} y2={h * f} className={styles.grade} />
        ))}

        {series.map((s, i) => {
          const d = caminho(s.valores, max, w, h)
          return (
            <g key={s.nome}>
              <path d={`${d} L ${w} ${h} L 0 ${h} Z`} fill={`url(#${id}-${i})`} />
              <path d={d} fill="none" stroke={s.cor} strokeWidth="2" vectorEffect="non-scaling-stroke" />
            </g>
          )
        })}
      </svg>

      <div className={styles.eixo}>
        {marcas.map((i) => (
          <span key={i} style={{ left: `${(i / Math.max(1, n - 1)) * 100}%` }}>
            {rotulos[i]}
          </span>
        ))}
      </div>
    </figure>
  )
}
