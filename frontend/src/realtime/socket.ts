/**
 * Uma conexão WebSocket por aba. Inscrições por canal, reconexão com backoff,
 * reinscrição automática ao reconectar.
 */
import { session } from '../api/client'

type Handler = (msg: Record<string, unknown>) => void

let ws: WebSocket | null = null
let connecting = false
let backoff = 1000
const handlers = new Map<string, Set<Handler>>()
const statusListeners = new Set<(s: 'open' | 'closed') => void>()

function url(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws?token=${encodeURIComponent(session.getAccessToken() ?? '')}`
}

function connect() {
  if (ws || connecting || !session.getAccessToken()) return
  connecting = true
  const socket = new WebSocket(url())
  socket.onopen = () => {
    connecting = false
    ws = socket
    backoff = 1000
    for (const channel of handlers.keys()) socket.send(JSON.stringify({ type: 'subscribe', channel }))
    statusListeners.forEach((l) => l('open'))
  }
  socket.onmessage = (ev) => {
    let msg: Record<string, unknown>
    try {
      msg = JSON.parse(ev.data as string) as Record<string, unknown>
    } catch {
      return
    }
    const channel = msg.channel as string | undefined
    if (channel) handlers.get(channel)?.forEach((h) => h(msg))
  }
  socket.onclose = () => {
    connecting = false
    ws = null
    statusListeners.forEach((l) => l('closed'))
    if (handlers.size > 0) {
      setTimeout(connect, backoff)
      backoff = Math.min(backoff * 2, 30_000)
    }
  }
  socket.onerror = () => socket.close()
}

export const realtime = {
  subscribe(channel: string, handler: Handler): () => void {
    let set = handlers.get(channel)
    const isNew = !set
    if (!set) {
      set = new Set()
      handlers.set(channel, set)
    }
    set.add(handler)
    if (ws?.readyState === WebSocket.OPEN) {
      if (isNew) ws.send(JSON.stringify({ type: 'subscribe', channel }))
    } else connect()
    return () => {
      const s = handlers.get(channel)
      s?.delete(handler)
      if (s && s.size === 0) {
        handlers.delete(channel)
        if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'unsubscribe', channel }))
      }
    }
  },
  onStatus(listener: (s: 'open' | 'closed') => void): () => void {
    statusListeners.add(listener)
    return () => statusListeners.delete(listener)
  },
  isOpen(): boolean {
    return ws?.readyState === WebSocket.OPEN
  },
}
