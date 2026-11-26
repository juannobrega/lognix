import { ApiError } from '../api/client'
import { Button } from './Button'
import { EmptyState } from './EmptyState'

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const api = error instanceof ApiError ? error : null
  return (
    <EmptyState title="Não foi possível carregar">
      <p>{api?.message ?? 'Falha ao falar com o servidor.'}</p>
      {api?.action && <p className="muted">{api.action}</p>}
      {onRetry && (
        <p style={{ marginTop: 'var(--space-4)' }}>
          <Button onClick={onRetry}>Tentar de novo</Button>
        </p>
      )}
    </EmptyState>
  )
}
