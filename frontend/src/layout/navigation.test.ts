import { describe, expect, it } from 'vitest'
import { SECTIONS, childFor, groupFor } from './navigation'

const grupos = SECTIONS.flatMap((s) => s.links).filter((l) => l.children)
const todos = SECTIONS.flatMap((s) => s.links)

describe('navegação', () => {
  it('nenhum caminho aparece duas vezes', () => {
    const caminhos = [...todos.map((l) => l.to), ...grupos.flatMap((g) => g.children ?? []).map((c) => c.to)]
    expect(new Set(caminhos).size).toBe(caminhos.length)
  })

  it('todo item tem rótulo e ícone', () => {
    for (const l of todos) {
      expect(l.label.length).toBeGreaterThan(0)
      expect(typeof l.icon).toBe('function')
    }
  })

  it('todo grupo tem descrição, e todo subitem também', () => {
    // As duas viram texto na tela: o grupo no subtítulo da entrada, o subitem no card.
    for (const g of grupos) {
      expect(g.description, `grupo ${g.label}`).toBeTruthy()
      for (const c of g.children ?? []) {
        expect(c.description, `subitem ${c.to}`).toBeTruthy()
      }
    }
  })

  it('todo subitem mora dentro do caminho do grupo', () => {
    // groupFor casa por prefixo; subitem fora do prefixo ficaria sem cabeçalho e sem card.
    for (const g of grupos) {
      for (const c of g.children ?? []) {
        expect(c.to.startsWith(`${g.to}/`), `${c.to} fora de ${g.to}`).toBe(true)
      }
    }
  })

  it('groupFor e childFor acham o que o cabeçalho precisa', () => {
    for (const g of grupos) {
      expect(groupFor(g.to)?.to).toBe(g.to)
      expect(childFor(g.to)).toBeUndefined() // a entrada do grupo não é subitem de si mesma
      for (const c of g.children ?? []) {
        expect(groupFor(c.to)?.to).toBe(g.to)
        expect(childFor(c.to)?.label).toBe(c.label)
      }
    }
  })

  it('a IA saiu de Configurações e levou Provedores, Consumo e MCP', () => {
    const ia = grupos.find((g) => g.to === '/ai')
    expect(ia?.children?.map((c) => c.to)).toEqual(['/ai/behavior', '/ai/providers', '/ai/usage', '/ai/mcp'])
    const config = grupos.find((g) => g.to === '/settings')
    expect(config?.children?.map((c) => c.to)).toEqual(['/settings/users', '/settings/system'])
  })
})
