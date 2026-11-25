import type { SVGProps } from 'react'

/**
 * Marcas dos provedores, desenhadas como SVG inline para não depender de CDN nem de imagem
 * externa. São representações simples, usadas só para identificar o serviço na interface.
 */

export function OpenRouterIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true" {...p}>
      <path
        d="M3 8h4.2a4 4 0 0 1 3.1 1.5l1.4 1.8A4 4 0 0 0 14.8 13H19"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M3 16h4.2a4 4 0 0 0 3.1-1.5l1.4-1.8A4 4 0 0 1 14.8 11H19"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path d="m17 5 4 3-4 3z" fill="currentColor" />
      <path d="m17 13 4 3-4 3z" fill="currentColor" />
    </svg>
  )
}

export function OpenAiIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true" {...p}>
      <g stroke="currentColor" strokeWidth="1.5">
        <ellipse cx="12" cy="12" rx="4.1" ry="9" />
        <ellipse cx="12" cy="12" rx="4.1" ry="9" transform="rotate(60 12 12)" />
        <ellipse cx="12" cy="12" rx="4.1" ry="9" transform="rotate(120 12 12)" />
      </g>
    </svg>
  )
}

export function BedrockIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true" {...p}>
      <path d="M4 7.5 12 3.5l8 4v9l-8 4-8-4z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M8 9.8v4.4l4 2.1 4-2.1V9.8l-4-2z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <path d="M2.6 19.4c3 1.4 6.1 2.1 9.4 2.1s6.4-.7 9.4-2.1" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

const BY_KIND: Record<string, (p: SVGProps<SVGSVGElement>) => JSX.Element> = {
  openrouter: OpenRouterIcon,
  openai: OpenAiIcon,
  bedrock: BedrockIcon,
}

export function ProviderIcon({ kind, ...rest }: { kind: string } & SVGProps<SVGSVGElement>) {
  const Component = BY_KIND[kind]
  if (!Component) {
    return (
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true" {...rest}>
        <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    )
  }
  return <Component {...rest} />
}
