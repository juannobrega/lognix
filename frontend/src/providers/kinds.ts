/**
 * Cor de cada marca, para o tile do ícone e o seletor de tipo. São tokens porque duas delas mudam
 * com o tema: ver `--brand-openrouter` e `--brand-openai` em `styles/tokens.css`.
 */
export const PROVIDER_TINT: Record<string, string> = {
  openrouter: 'var(--brand-openrouter)',
  openai: 'var(--brand-openai)',
  bedrock: 'var(--brand-bedrock)',
}
