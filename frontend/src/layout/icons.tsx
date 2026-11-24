import type { SVGProps } from 'react'

/** Ícones de contorno, traço 1.5px, 16px. Mesma família para tudo. */
const base: SVGProps<SVGSVGElement> = {
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
}

export const Icons = {
  dashboard: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <rect x="3" y="3" width="7.5" height="7.5" rx="2" />
      <rect x="13.5" y="3" width="7.5" height="4.5" rx="2" />
      <rect x="13.5" y="10.5" width="7.5" height="10.5" rx="2" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="2" />
    </svg>
  ),
  server: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <rect x="3" y="4" width="18" height="7" rx="2" />
      <rect x="3" y="13" width="18" height="7" rx="2" />
      <path d="M7 7.5h.01M7 16.5h.01" />
    </svg>
  ),
  box: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <path d="M21 8.5 12 4 3 8.5v7L12 20l9-4.5z" />
      <path d="M3 8.5 12 13l9-4.5M12 13v7" />
    </svg>
  ),
  spark: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.8 5.8l1.8 1.8M16.4 16.4l1.8 1.8M5.8 18.2l1.8-1.8M16.4 7.6l1.8-1.8" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ),
  bell: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <path d="M6 9.5a6 6 0 0 1 12 0V13l1.6 2.5H4.4L6 13z" />
      <path d="M10 18.5a2 2 0 0 0 4 0" />
    </svg>
  ),
  settings: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.1 14.5a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.2a1.7 1.7 0 0 0-2.9-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H3a2 2 0 1 1 0-4h.2a1.7 1.7 0 0 0 1.1-2.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 2.9-1.2V3a2 2 0 1 1 4 0v.2a1.7 1.7 0 0 0 2.9 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0 1.2 2.9H21a2 2 0 1 1 0 4h-.2a1.7 1.7 0 0 0-1.6 1z" />
    </svg>
  ),
  sun: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ),
  moon: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  ),
  logout: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </svg>
  ),
  plus: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  ),
  search: (p: SVGProps<SVGSVGElement>) => (
    <svg {...base} {...p}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  ),
}
