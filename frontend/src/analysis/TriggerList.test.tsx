import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { TriggerFired } from '../api/types'
import { TriggerList } from './TriggerList'

const base: TriggerFired = {
  id: 't1',
  analysis_run_id: 1,
  container_id: 'c1',
  type: 'error',
  reason: { error_lines: 3 },
  fired_at: '2026-11-24T10:00:00Z',
  window_start: '2026-11-24T09:59:30Z',
  window_end: '2026-11-24T10:00:00Z',
  sample_lines: [{ ts_ns: '1', line: 'ERROR db down' }],
  note: '3 linha(s) de erro na janela',
  insight_id: null,
  container_name: 'api',
  host_name: 'vm-01',
}

function renderList(triggers: TriggerFired[], showProject = true) {
  return render(
    <MemoryRouter>
      <TriggerList triggers={triggers} showProject={showProject} />
    </MemoryRouter>,
  )
}

describe('TriggerList', () => {
  it('mostra estado vazio sem ocorrências', () => {
    renderList([])
    expect(screen.getByText('Nenhuma ocorrência')).toBeInTheDocument()
  })

  it('mostra tipo, projeto e amostra de erro', () => {
    renderList([base])
    expect(screen.getByText('erro')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'api' })).toHaveAttribute('href', '/projects/c1')
    expect(screen.getByText('3 linha(s) de erro na janela')).toBeInTheDocument()
    expect(screen.getByText('1 linha(s) de erro')).toBeInTheDocument()
  })

  it('omite o projeto quando já estamos nele', () => {
    renderList([base], false)
    expect(screen.queryByRole('link', { name: 'api' })).not.toBeInTheDocument()
  })
})
