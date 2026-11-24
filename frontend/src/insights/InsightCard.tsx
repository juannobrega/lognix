import { Link } from 'react-router-dom'
import type { Insight } from '../api/types'
import { dateTime } from '../components/format'
import { LOW_CONFIDENCE, SEVERITY_COLOR, SEVERITY_LABEL, TRIGGER_LABEL } from './severity'
import styles from './InsightCard.module.css'

export function InsightCard({ insight }: { insight: Insight }) {
  const low = insight.confidence < LOW_CONFIDENCE
  return (
    <Link to={`/insights/${insight.id}`} className={styles.card}>
      <div className={styles.head}>
        <span className={styles.severity} style={{ color: SEVERITY_COLOR[insight.severity] }}>
          {SEVERITY_LABEL[insight.severity]}
        </span>
        {insight.container_name && <strong>{insight.container_name}</strong>}
        {insight.host_name && <span className="muted">{insight.host_name}</span>}
        <span style={{ marginLeft: 'auto' }} className="muted">
          {dateTime(insight.created_at)}
        </span>
      </div>
      <h3 className={styles.title}>{insight.title}</h3>
      <p className={styles.summary}>{insight.summary}</p>
      <div className={styles.meta}>
        {insight.trigger_type && <span>trigger: {TRIGGER_LABEL[insight.trigger_type]}</span>}
        <span className={low ? styles.lowConfidence : undefined}>
          confiança {(insight.confidence * 100).toFixed(0)}%{low ? ' · baixa' : ''}
        </span>
        <span>{insight.evidence.length} evidência(s)</span>
        {insight.needs_code && <span>causa provável no código</span>}
        {insight.context_truncated && <span>contexto cortado por limite de tokens</span>}
      </div>
    </Link>
  )
}
