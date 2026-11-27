import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Switch } from './Switch'

describe('Switch', () => {
  it('se move no clique, antes de a resposta chegar', async () => {
    const user = userEvent.setup()
    // `checked` fixo em false é o servidor que ainda não respondeu.
    render(<Switch checked={false} pending onCheckedChange={vi.fn()} aria-label="x" />)
    await user.click(screen.getByLabelText('x'))
    expect(screen.getByLabelText('x')).toBeChecked()
  })

  it('volta sozinho quando a mutação termina sem mudar nada', async () => {
    const user = userEvent.setup()

    function Tela() {
      const [pendente, setPendente] = useState(false)
      return (
        <>
          <Switch checked={false} pending={pendente} onCheckedChange={() => setPendente(true)} aria-label="x" />
          <button onClick={() => setPendente(false)}>falhou</button>
        </>
      )
    }

    render(<Tela />)
    await user.click(screen.getByLabelText('x'))
    expect(screen.getByLabelText('x')).toBeChecked()
    // A mutação terminou e `checked` continua false: foi erro, e o interruptor não pode mentir.
    await user.click(screen.getByRole('button', { name: 'falhou' }))
    expect(screen.getByLabelText('x')).not.toBeChecked()
  })

  it('desabilitado não aceita clique', async () => {
    const user = userEvent.setup()
    const mudou = vi.fn()
    render(<Switch checked={false} disabled onCheckedChange={mudou} aria-label="x" />)
    await user.click(screen.getByLabelText('x'))
    expect(mudou).not.toHaveBeenCalled()
  })

  it('a posição do polegar é calculada a partir do trilho, não chutada', () => {
    // O jsdom não tem layout, então geometria não dá para medir aqui. O que dá para garantir é
    // que o deslocamento continua derivado das mesmas medidas: quando era um número solto, o
    // polegar vazava 3px para fora do trilho ligado e parava no meio dele desligado.
    const css = readFileSync(join(process.cwd(), 'src/ui/Switch.module.css'), 'utf8')
    const ligado = css.match(/\.thumb\[data-state='checked'\]\s*\{([^}]*)\}/)?.[1] ?? ''
    expect(ligado).toContain('calc(')
    expect(ligado).toContain('var(--trilho-l)')
    expect(ligado).toContain('var(--polegar)')
    expect(ligado).toMatch(/var\(--folga\)/)
  })
})
