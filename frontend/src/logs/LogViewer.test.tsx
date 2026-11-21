import { render, screen } from '@testing-library/react'
import { isErrorLine } from './errorPattern'
import { LogViewer } from './LogViewer'

describe('LogViewer', () => {
  it('destaca linhas de erro pelo padrão', () => {
    expect(isErrorLine('2026 ERROR db down')).toBe(true)
    expect(isErrorLine('Traceback (most recent call last):')).toBe(true)
    expect(isErrorLine('GET /health 200')).toBe(false)
  })

  it('mostra estado vazio quando não há linhas', () => {
    render(<LogViewer lines={[]} follow empty={<span>Aguardando as primeiras linhas.</span>} />)
    expect(screen.getByText('Aguardando as primeiras linhas.')).toBeInTheDocument()
  })
})
