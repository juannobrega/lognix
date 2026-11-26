import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

// vitest roda a partir de `frontend/`.
const SRC = join(process.cwd(), 'src')

function cssFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) return cssFiles(full)
    return full.endsWith('.css') ? [full] : []
  })
}

function scale(): Record<string, number> {
  const tokens = readFileSync(join(SRC, 'styles/tokens.css'), 'utf8')
  const found: Record<string, number> = {}
  for (const [, name, value] of tokens.matchAll(/--(z-[a-z]+):\s*(\d+);/g)) found[name] = Number(value)
  return found
}

/**
 * O empilhamento é invariante de arquitetura, não gosto: um Select dentro de um diálogo precisa
 * pintar sobre ele. Já quebrou uma vez — o menu abria atrás do modal e parecia não abrir —, e
 * jsdom não tem layout, então nenhum teste de componente pega isso. Aqui a regra é verificada
 * na fonte.
 */
describe('escala de empilhamento', () => {
  it('sobe na ordem em que as camadas se cobrem', () => {
    const z = scale()
    const order = ['z-sticky', 'z-docked', 'z-modal', 'z-popup', 'z-tooltip', 'z-toast']
    for (const name of order) expect(z[name], `${name} não está definido em tokens.css`).toBeTypeOf('number')
    const values = order.map((n) => z[n])
    expect(values, `esperado crescente: ${order.join(' < ')}`).toEqual([...values].sort((a, b) => a - b))
    expect(new Set(values).size, 'duas camadas com o mesmo valor empatam na ordem de pintura').toBe(values.length)
  })

  it('o que abre fica acima de quem abriu', () => {
    const z = scale()
    expect(z['z-popup']).toBeGreaterThan(z['z-modal'])
    expect(z['z-tooltip']).toBeGreaterThan(z['z-popup'])
  })

  it('nenhum componente escreve z-index na mão', () => {
    const offenders = cssFiles(SRC)
      .filter((f) => !f.endsWith('tokens.css'))
      .flatMap((f) => [...readFileSync(f, 'utf8').matchAll(/z-index:\s*(\d+)/g)].map((m) => `${f.replace(SRC, '')}: ${m[0]}`))
    expect(offenders, 'use var(--z-*): valores soltos não têm como ser comparados entre si').toEqual([])
  })
})
