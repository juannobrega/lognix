import { useEffect, useMemo, useState } from 'react'
import type { Container } from '../api/types'
import { Button } from '../components/Button'
import { ContainerStateBadge } from '../components/StatusBadge'
import styles from './ContainerPicker.module.css'

interface Props {
  containers: Container[]
  onSave: (ids: string[]) => void
  saving: boolean
}

export function ContainerPicker({ containers, onSave, saving }: Props) {
  const initial = useMemo(() => new Set(containers.filter((c) => c.monitored).map((c) => c.id)), [containers])
  const [selected, setSelected] = useState<Set<string>>(initial)
  useEffect(() => setSelected(initial), [initial])

  const dirty = selected.size !== initial.size || [...selected].some((id) => !initial.has(id))
  const projects = [...new Set(containers.map((c) => c.compose_project).filter(Boolean))] as string[]

  function toggle(id: string) {
    setSelected((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  }
  function selectProject(p: string) {
    setSelected((s) => new Set([...s, ...containers.filter((c) => c.compose_project === p).map((c) => c.id)]))
  }

  return (
    <>
      <div className={styles.bar}>
        <Button variant="ghost" onClick={() => setSelected(new Set(containers.map((c) => c.id)))}>
          Selecionar todos
        </Button>
        <Button variant="ghost" onClick={() => setSelected(new Set())}>
          Limpar
        </Button>
        {projects.map((p) => (
          <Button key={p} variant="ghost" onClick={() => selectProject(p)}>
            + projeto {p}
          </Button>
        ))}
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Monitorar</th>
            <th>Nome</th>
            <th>Imagem</th>
            <th>Estado</th>
            <th>Compose</th>
            <th>Desde</th>
          </tr>
        </thead>
        <tbody>
          {containers.map((c) => (
            <tr key={c.id}>
              <td>
                <input
                  type="checkbox"
                  aria-label={`Monitorar ${c.name}`}
                  checked={selected.has(c.id)}
                  onChange={() => toggle(c.id)}
                />
              </td>
              <td>{c.name}</td>
              <td className={styles.mono}>{c.image}</td>
              <td>
                <ContainerStateBadge state={c.state} />
              </td>
              <td className={styles.muted}>{c.compose_project ? `${c.compose_project} / ${c.compose_service ?? ''}` : '—'}</td>
              <td className={styles.muted}>{c.monitored_since ? new Date(c.monitored_since).toLocaleString('pt-BR') : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className={styles.bar}>
        <Button variant="primary" disabled={!dirty} loading={saving} onClick={() => onSave([...selected])}>
          Salvar monitoramento
        </Button>
        {dirty && <span className={styles.notice}>A coleta começa agora. Logs anteriores à marcação não são coletados.</span>}
      </div>
    </>
  )
}
