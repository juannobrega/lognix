const ERROR_RE = /\b(ERROR|FATAL|CRITICAL|Exception|Traceback|panic|\[error\])\b/

/** Destaque visual de linhas de erro. A classificação de verdade é do backend (fase 0.6.0). */
export function isErrorLine(line: string): boolean {
  return ERROR_RE.test(line)
}
