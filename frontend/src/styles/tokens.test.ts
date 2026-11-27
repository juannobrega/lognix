import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const SRC = join(process.cwd(), 'src')

/** Definidas em tempo de execução pelo componente, não em tokens.css. */
const LOCAIS = new Set(['--tint'])

function cssFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((e) => {
    const full = join(dir, e)
    return statSync(full).isDirectory() ? cssFiles(full) : full.endsWith('.css') ? [full] : []
  })
}

/**
 * Token que não existe é declaração inválida, e declaração inválida o browser simplesmente
 * descarta — sem erro no console, sem aviso no build, sem nada falhar.
 *
 * Aconteceu: `--card-border` e `--radius-card` nunca foram definidos, e dez arquivos os usavam.
 * O resultado era diálogo de canto reto e componente sem borda, por meses, com todo o lint e
 * todo o typecheck verdes. CSS não tem compilador que pegue isso; este teste tem.
 */
describe('tokens de estilo', () => {
  const declarados = new Set(
    [...readFileSync(join(SRC, 'styles/tokens.css'), 'utf8').matchAll(/^\s*(--[\w-]+):/gm)].map(
      (m) => m[1],
    ),
  )

  it('tokens.css declara algo', () => {
    expect(declarados.size).toBeGreaterThan(30)
  })

  it('todo var(--token) aponta para um token que existe', () => {
    const orfas: string[] = []
    for (const arquivo of cssFiles(SRC)) {
      const texto = readFileSync(arquivo, 'utf8')
      // Variável declarada no próprio arquivo é local por desenho — o Switch calcula a posição
      // do polegar a partir das dimensões do trilho, e esses números não são token de tema.
      const noArquivo = new Set([...texto.matchAll(/^\s*(--[\w-]+):/gm)].map((m) => m[1]))
      for (const [, nome] of texto.matchAll(/var\((--[\w-]+)/g)) {
        // Variáveis locais, que o componente passa por style={{ '--tint': ... }}, e as que o
        // próprio Radix injeta no elemento. Nenhuma das duas mora em tokens.css.
        if (LOCAIS.has(nome) || noArquivo.has(nome) || nome.startsWith('--radix-')) continue
        if (!declarados.has(nome)) orfas.push(`${arquivo.replace(SRC, '')}: ${nome}`)
      }
    }
    expect([...new Set(orfas)], 'o browser descarta a regra inteira em silêncio').toEqual([])
  })
})
