import type { SVGProps } from 'react'

/**
 * Marca do Model Context Protocol.
 *
 * Geometria tirada do ativo oficial, https://modelcontextprotocol.io/favicon.svg — os três
 * traços, sem o quadrado preto de fundo. O `viewBox` continua 180, como no original, porque
 * reescalar os pontos à mão é justamente o jeito de a marca sair torta: cor e tamanho mudam,
 * a geometria não.
 *
 * Em 20px o traço de 11.0667 renderiza a ~1.48px, que é o 1.5 da família de ícones do projeto.
 * É marca registrada de seu dono, e aparece aqui só para identificar o protocolo.
 */
export function McpMark(p: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 180 180"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="11.0667"
      strokeLinecap="round"
      aria-hidden="true"
      {...p}
    >
      <path d="M23.5996 85.2532L86.2021 22.6507C94.8457 14.0071 108.86 14.0071 117.503 22.6507C126.147 31.2942 126.147 45.3083 117.503 53.9519L70.2254 101.23" />
      <path d="M70.8789 100.578L117.504 53.952C126.148 45.3083 140.163 45.3083 148.806 53.952L149.132 54.278C157.776 62.9216 157.776 76.9357 149.132 85.5792L92.5139 142.198C89.6327 145.079 89.6327 149.75 92.5139 152.631L104.14 164.257" />
      <path d="M101.853 38.3013L55.553 84.6011C46.9094 93.2447 46.9094 107.258 55.553 115.902C64.1966 124.546 78.2106 124.546 86.8543 115.902L133.154 69.6025" />
    </svg>
  )
}
