import { EmptyState } from '../components/EmptyState'

export function PlaceholderPage({ title, phase }: { title: string; phase: string }) {
  return (
    <>
      <div className="page-header">
        <div>
          <h1>{title}</h1>
        </div>
      </div>
      <EmptyState title={`Disponível na fase ${phase}`}>
        <p>Esta área ainda não foi construída. O roadmap completo está no repositório.</p>
      </EmptyState>
    </>
  )
}
