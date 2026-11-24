import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from './Button'
import { ToastProvider } from './Toast'
import { useToast } from './useToast'

function Trigger() {
  const toast = useToast()
  return <Button onClick={() => toast.show('Salvo com sucesso', 'success')}>Salvar</Button>
}

describe('Toast', () => {
  it('mostra e fecha um aviso', async () => {
    const user = userEvent.setup()
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    )
    expect(screen.queryByText('Salvo com sucesso')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(screen.getByText('Salvo com sucesso')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Fechar aviso' }))
    expect(screen.queryByText('Salvo com sucesso')).not.toBeInTheDocument()
  })
})
