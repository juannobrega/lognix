import { render, screen } from '@testing-library/react'
import { Field } from './Field'

describe('Field', () => {
  it('liga rótulo ao input e expõe erro acessível', () => {
    render(<Field label="E-mail" error="Inválido" />)
    const input = screen.getByLabelText('E-mail')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent('Inválido')
  })
})
