import { bytes, compact, duration, tokens, usd } from './format'

describe('format', () => {
  it('compacta números grandes', () => {
    expect(compact(0)).toBe('0')
    expect(compact(999)).toBe('999')
    expect(compact(1500)).toBe('1.5 mil')
    expect(compact(42_000)).toBe('42 mil')
    expect(compact(2_400_000)).toBe('2.4 mi')
  })

  it('formata bytes', () => {
    expect(bytes(null)).toBe('—')
    expect(bytes(512)).toBe('512 B')
    expect(bytes(2048)).toBe('2.0 KB')
    expect(bytes(5 * 1024 ** 3)).toBe('5.0 GB')
  })

  it('formata duração', () => {
    expect(duration(45)).toBe('45s')
    expect(duration(120)).toBe('2min')
    expect(duration(3700)).toBe('1h 1min')
    expect(duration(90_000)).toBe('1d 1h')
  })

  it('formata custo em dólares', () => {
    expect(usd(0)).toBe('$0,00')
    expect(usd('0.0042')).toBe('$0,0042')
    expect(usd(1.5)).toBe('$1,50')
    expect(usd('abc')).toBe('—')
  })

  it('formata tokens', () => {
    expect(tokens(900)).toBe('900')
    expect(tokens(1500)).toBe('1.5k')
    expect(tokens(42_000)).toBe('42k')
  })
})
