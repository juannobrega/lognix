import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { LogLine, LogsResponse } from '../api/types'
import { realtime } from '../realtime/socket'

export type Period = '15m' | '1h' | '6h' | '24h' | '7d'
const PERIOD_MS: Record<Period, number> = { '15m': 15 * 60e3, '1h': 3600e3, '6h': 6 * 3600e3, '24h': 24 * 3600e3, '7d': 7 * 24 * 3600e3 }
const MAX_LIVE_LINES = 5000

interface State {
  lines: LogLine[]
  loading: boolean
  error: ApiError | null
  hasMore: boolean
  truncated: boolean
  monitoredSince: string | null
}

export function useProjectLogs(projectId: string, opts: { live: boolean; period: Period; text: string }) {
  const [state, setState] = useState<State>({ lines: [], loading: true, error: null, hasMore: false, truncated: false, monitoredSince: null })
  const oldestRef = useRef<string | null>(null)
  const seen = useRef(new Set<string>())

  const key = (ln: LogLine) => `${ln.ts_ns}|${ln.line}`

  const load = useCallback(
    async (opts2: { before?: string | null } = {}) => {
      setState((s) => ({ ...s, loading: true, error: null }))
      const end = opts2.before ? new Date(Number(BigInt(opts2.before) / 1_000_000n)) : new Date()
      const start = new Date(Date.now() - PERIOD_MS[opts.period])
      try {
        const params = new URLSearchParams({ start: start.toISOString(), end: end.toISOString(), limit: '500', direction: 'backward' })
        if (opts.text) params.set('q', opts.text)
        const res = await api<LogsResponse>(`/projects/${projectId}/logs?${params}`)
        setState((s) => {
          const incoming = res.lines.filter((ln) => !seen.current.has(key(ln)))
          incoming.forEach((ln) => seen.current.add(key(ln)))
          const lines = opts2.before ? [...incoming, ...s.lines] : incoming
          return { ...s, lines, loading: false, hasMore: res.has_more, monitoredSince: res.monitored_since }
        })
        oldestRef.current = res.oldest_ts_ns
      } catch (err) {
        setState((s) => ({ ...s, loading: false, error: err instanceof ApiError ? err : new ApiError(0, 'network', 'Falha ao consultar logs.') }))
      }
    },
    [projectId, opts.period, opts.text],
  )

  // Recarrega quando filtros mudam.
  useEffect(() => {
    seen.current.clear()
    oldestRef.current = null
    void load()
  }, [load])

  // Ao vivo: inscreve no canal.
  useEffect(() => {
    if (!opts.live) return
    const channel = `logs:${projectId}`
    return realtime.subscribe(channel, (msg) => {
      if (msg.type !== 'lines') return
      const incoming = (msg.lines as LogLine[]).filter((ln) => !seen.current.has(key(ln)) && (!opts.text || ln.line.includes(opts.text)))
      if (incoming.length === 0) return
      incoming.forEach((ln) => seen.current.add(key(ln)))
      setState((s) => {
        let lines = [...s.lines, ...incoming]
        let truncated = s.truncated
        if (lines.length > MAX_LIVE_LINES) {
          lines = lines.slice(lines.length - MAX_LIVE_LINES)
          truncated = true
        }
        return { ...s, lines, truncated }
      })
    })
  }, [projectId, opts.live, opts.text])

  const loadOlder = useCallback(() => {
    if (state.loading || !state.hasMore || !oldestRef.current) return
    void load({ before: oldestRef.current })
  }, [load, state.loading, state.hasMore])

  return { ...state, loadOlder, reload: () => void load() }
}
