import { useVirtualizer } from '@tanstack/react-virtual'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { LogLine } from '../api/types'
import { isErrorLine } from './errorPattern'
import styles from './LogViewer.module.css'

function fmt(tsNs: string): string {
  const ms = Number(BigInt(tsNs) / 1_000_000n)
  const d = new Date(ms)
  return `${d.toLocaleTimeString('pt-BR', { hour12: false })}.${String(ms % 1000).padStart(3, '0')}`
}

interface Props {
  lines: LogLine[]
  follow: boolean
  onFollowChange?: (follow: boolean) => void
  empty?: ReactNode
  onReachTop?: () => void
}

export function LogViewer({ lines, follow, onFollowChange, empty, onReachTop }: Props) {
  const parentRef = useRef<HTMLDivElement>(null)
  const [pendingCount, setPendingCount] = useState(0)
  const lastLen = useRef(lines.length)

  const virtualizer = useVirtualizer({
    count: lines.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 21,
    overscan: 30,
  })

  useEffect(() => {
    const added = lines.length - lastLen.current
    lastLen.current = lines.length
    if (lines.length === 0) return
    if (follow) {
      virtualizer.scrollToIndex(lines.length - 1, { align: 'end' })
      setPendingCount(0)
    } else if (added > 0) {
      setPendingCount((n) => n + added)
    }
  }, [lines.length, follow, virtualizer])

  function onScroll() {
    const el = parentRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 8
    if (atBottom && !follow) {
      onFollowChange?.(true)
      setPendingCount(0)
    } else if (!atBottom && follow) {
      onFollowChange?.(false)
    }
    if (el.scrollTop < 40) onReachTop?.()
  }

  return (
    <div ref={parentRef} className={styles.viewer} onScroll={onScroll} role="log" aria-live="off" tabIndex={0}>
      {lines.length === 0 && <div className={styles.empty}>{empty}</div>}
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map((item) => {
          const ln = lines[item.index]
          const err = isErrorLine(ln.line)
          return (
            <div
              key={item.key}
              ref={virtualizer.measureElement}
              data-index={item.index}
              className={[styles.row, err ? styles.error : ''].join(' ')}
              style={{ position: 'absolute', top: 0, left: 0, width: '100%', transform: `translateY(${item.start}px)` }}
              title={Object.entries(ln.labels)
                .map(([k, v]) => `${k}=${v}`)
                .join('\n')}
            >
              <span className={styles.ts}>{fmt(ln.ts_ns)}</span>
              <span className={styles.text}>{ln.line}</span>
            </div>
          )
        })}
      </div>
      {!follow && pendingCount > 0 && (
        <button
          className={styles.toFoot}
          onClick={() => {
            onFollowChange?.(true)
            virtualizer.scrollToIndex(lines.length - 1, { align: 'end' })
            setPendingCount(0)
          }}
        >
          ↓ {pendingCount} novas
        </button>
      )}
    </div>
  )
}
