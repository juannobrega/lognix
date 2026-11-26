import styles from './Skeleton.module.css'

export function Skeleton({ width = '100%', height = 16 }: { width?: string | number; height?: number }) {
  return <div className={styles.skeleton} style={{ width, height }} aria-hidden="true" />
}

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className={styles.rows} role="status" aria-label="Carregando">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} width={`${90 - i * 8}%`} />
      ))}
    </div>
  )
}
