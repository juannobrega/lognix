/**
 * Cor de cada marca, para o tile do ícone e o seletor de tipo. São tokens porque duas delas mudam
 * com o tema: ver `--brand-openrouter` e `--brand-openai` em `styles/tokens.css`.
 */
export const PROVIDER_TINT: Record<string, string> = {
  openrouter: 'var(--brand-openrouter)',
  openai: 'var(--brand-openai)',
  bedrock: 'var(--brand-bedrock)',
  // Cores publicadas por cada fabricante. As monocromáticas por definição seguem o texto.
  anthropic: '#d97757',
  gemini: '#3186ff',
  groq: '#f55036',
  mistral: '#fa500f',
  deepseek: '#4d6bfe',
  xai: 'var(--brand-openai)',
  together: '#0f6fff',
  fireworks: '#5019c5',
  cerebras: '#f15a29',
  perplexity: '#22b8cd',
  ollama: 'var(--brand-openai)',
  custom: 'var(--accent)',
}
