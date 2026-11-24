import type { Severity } from '../api/types'

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'crítico',
  high: 'alto',
  medium: 'médio',
  low: 'baixo',
  info: 'informativo',
}

export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: 'var(--sev-critical)',
  high: 'var(--sev-high)',
  medium: 'var(--sev-medium)',
  low: 'var(--sev-low)',
  info: 'var(--sev-info)',
}

export const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low', 'info']

/** Abaixo disto a interface marca o insight como de baixa confiança. Guardrails seção 2. */
export const LOW_CONFIDENCE = 0.4

export const TRIGGER_LABEL: Record<string, string> = {
  error: 'erro',
  docker_event: 'evento Docker',
  anomaly: 'anomalia',
  manual: 'manual',
}
