import * as Popover from '@radix-ui/react-popover'
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react'
import styles from './Combobox.module.css'

export interface ComboboxOption {
  value: string
  label: string
  /** Texto à direita, alinhado: preço, contagem, o que diferencia uma opção da outra. */
  hint?: ReactNode
  icon?: ReactNode
  disabled?: boolean
}

interface Props {
  options: ComboboxOption[]
  onSelect: (value: string) => void
  /** Texto do gatilho quando nada foi escolhido. */
  placeholder: string
  searchPlaceholder?: string
  /** Mostrado em destaque: a opção que já vale hoje. */
  value?: string | null
  disabled?: boolean
  loading?: boolean
  emptyLabel?: string
  'aria-label': string
}

/**
 * Escolha de um item numa lista longa: abre, filtra pelo que se digita, anda pelo teclado.
 *
 * Existe porque `Select` não filtra, e as listas de modelo de um provider passam de trezentas
 * entradas — rolar até achar não é escolher.
 */
export function Combobox({
  options,
  onSelect,
  placeholder,
  searchPlaceholder = 'buscar',
  value,
  disabled,
  loading,
  emptyLabel = 'Nada encontrado.',
  ...aria
}: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const listId = useId()
  const listRef = useRef<HTMLUListElement>(null)

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return options
    return options.filter((o) => o.value.toLowerCase().includes(needle) || o.label.toLowerCase().includes(needle))
  }, [options, query])

  // Filtrar muda a lista debaixo do cursor; sem isto o destaque fica numa linha que saiu.
  useEffect(() => setActive(0), [query, open])

  useEffect(() => {
    if (!open) return
    listRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  function choose(option: ComboboxOption | undefined) {
    if (!option || option.disabled) return
    onSelect(option.value)
    setOpen(false)
    setQuery('')
  }

  const current = options.find((o) => o.value === value)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button type="button" className={styles.trigger} disabled={disabled} aria-label={aria['aria-label']}>
          {current ? (
            <span className="row" style={{ gap: 8, flexWrap: 'nowrap', minWidth: 0 }}>
              {current.icon}
              <span className={styles.optionLabel}>{current.label}</span>
            </span>
          ) : (
            <span className={styles.placeholder}>{loading ? 'carregando…' : placeholder}</span>
          )}
          <svg className={styles.chevron} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className={styles.content} sideOffset={4} align="start">
          <div className={styles.search}>
            <input
              autoFocus
              value={query}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              aria-controls={listId}
              aria-activedescendant={shown[active] ? `${listId}-${active}` : undefined}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') {
                  e.preventDefault()
                  setActive((i) => Math.min(i + 1, shown.length - 1))
                } else if (e.key === 'ArrowUp') {
                  e.preventDefault()
                  setActive((i) => Math.max(i - 1, 0))
                } else if (e.key === 'Enter') {
                  e.preventDefault()
                  choose(shown[active])
                }
              }}
            />
          </div>
          {shown.length === 0 ? (
            <p className={styles.empty}>{emptyLabel}</p>
          ) : (
            <ul className={styles.list} id={listId} role="listbox" ref={listRef} aria-label={aria['aria-label']}>
              {shown.slice(0, 200).map((o, i) => (
                <li
                  key={o.value}
                  id={`${listId}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  aria-disabled={o.disabled || undefined}
                  data-current={o.value === value || undefined}
                  className={styles.option}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => choose(o)}
                >
                  {o.icon}
                  <span className={styles.optionMain}>
                    <span className={styles.optionLabel}>{o.label}</span>
                  </span>
                  {o.hint && <span className={styles.optionHint}>{o.hint}</span>}
                </li>
              ))}
            </ul>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
