import { bytes, compact, duration } from './format'

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
})
