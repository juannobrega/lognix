import { Link } from 'react-router-dom'
import type { NavChild } from './navigation'
import styles from './SectionHub.module.css'

/**
 * Tela de entrada de um grupo de navegação: um card por subpágina.
 *
 * Existe porque clicar no pai tinha que levar a algum lugar. Redirecionar para a primeira
 * subpágina escondia as outras e fazia parecer que "Configurações" era sinônimo de "Usuários".
 */
export function SectionHub({ items }: { items: NavChild[] }) {
  return (
    <div className={styles.grid}>
      {items.map((item) => (
        <Link key={item.to} to={item.to} className={styles.card}>
          <span className={styles.tile}>
            <item.icon width={18} height={18} />
          </span>
          <span>
            <h2 className={styles.title}>{item.label}</h2>
            <p className={styles.description}>{item.description}</p>
          </span>
        </Link>
      ))}
    </div>
  )
}
