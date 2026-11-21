import { EmptyState } from '../components/EmptyState'

export function PlaceholderPage({ title, phase }: { title: string; phase: string }) {
  return (
    <>
      <h1>{title}</h1>
      <EmptyState title={`Disponível na fase ${phase}`} />
    </>
  )
}
