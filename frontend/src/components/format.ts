/** Formatações compartilhadas entre componentes. Fora do módulo de componente por Fast Refresh. */

export function compact(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)} mil`
  return `${(n / 1_000_000).toFixed(1)} mi`
}

export function bytes(n: number | null): string {
  if (n === null) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = n
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export function duration(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}min`
  if (m > 0) return `${m}min`
  return `${seconds}s`
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR')
}

export function timeOnly(iso: string): string {
  return new Date(iso).toLocaleTimeString('pt-BR')
}

/** Custo em dólares. Mostra centavos de milésimo quando o valor é pequeno. */
export function usd(value: string | number): string {
  const n = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(n)) return '—'
  if (n === 0) return '$0,00'
  if (n < 0.01) return `$${n.toFixed(4).replace('.', ',')}`
  return `$${n.toFixed(2).replace('.', ',')}`
}

export function tokens(n: number): string {
  if (n < 1000) return String(n)
  return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}k`
}
