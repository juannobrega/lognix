import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// O jsdom não implementa captura de ponteiro nem rolagem, e os componentes do Radix que abrem
// camada — Select, Dropdown — chamam as duas ao abrir. Sem estes retalhos, o menu nunca abre no
// teste e a falha aparece como "não achei a opção", que manda procurar no lugar errado.
Object.assign(window.HTMLElement.prototype, {
  hasPointerCapture: vi.fn(() => false),
  setPointerCapture: vi.fn(),
  releasePointerCapture: vi.fn(),
  scrollIntoView: vi.fn(),
})
