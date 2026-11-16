import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

import { CheckIcon, ChevronDownIcon, SearchIcon } from './icons'
import './dropdown.css'

export interface DropdownOption {
  value: string
  label: string
}

interface DropdownProps {
  /** Nome do filtro; aparece no botão ("Período: Nov 2026"). */
  label: string
  icon?: ReactNode
  options: DropdownOption[]
  value: string
  onChange: (value: string) => void
  /** Valor que significa "sem filtro": o botão só ganha destaque quando o valor é outro. */
  emptyValue?: string
  /** Mostra uma busca no topo da lista (para listas longas, como clínicas). */
  searchable?: boolean
  disabled?: boolean
  className?: string
  /** `filter` (padrão): botão compacto "Rótulo: valor". `field`: campo de formulário com rótulo acima. */
  variant?: 'filter' | 'field'
  /** Só no `field`: texto quando nada está selecionado. */
  placeholder?: string
  errorMessage?: string
}

function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

interface PopoverPosition {
  top: number
  left: number
  minWidth: number
  maxHeight: number
}

/** Menu suspenso próprio (o `<select>` nativo não aceita estilo). Listbox acessível com teclado:
 * setas, Home/End, Enter, Esc; foco volta ao botão ao fechar. A lista vai para o `body` para não
 * ser cortada por painéis com `overflow: hidden`. */
export function Dropdown({
  label,
  icon,
  options,
  value,
  onChange,
  emptyValue = '',
  searchable = false,
  disabled = false,
  className,
  variant = 'filter',
  placeholder = 'Selecione…',
  errorMessage,
}: DropdownProps) {
  const baseId = useId()
  const listboxId = `${baseId}-listbox`
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const [position, setPosition] = useState<PopoverPosition | null>(null)

  const visibleOptions = useMemo(() => {
    if (!searchable || !query.trim()) return options
    const needle = normalize(query.trim())
    return options.filter((option) => normalize(option.label).includes(needle))
  }, [options, query, searchable])

  const isField = variant === 'field'
  const selected = isField
    ? options.find((option) => option.value === value)
    : (options.find((option) => option.value === value) ?? options[0])
  const isActive = !isField && value !== emptyValue
  const labelId = `${baseId}-label`
  const textId = `${baseId}-text`

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const width = Math.max(rect.width, 224)
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8))
    const top = rect.bottom + 4
    setPosition({
      top,
      left,
      minWidth: width,
      maxHeight: Math.max(160, Math.min(352, window.innerHeight - top - 12)),
    })
  }, [])

  function openMenu() {
    if (disabled) return
    const index = options.findIndex((option) => option.value === value)
    setQuery('')
    setActiveIndex(Math.max(0, index))
    updatePosition()
    setOpen(true)
  }

  function closeMenu(restoreFocus: boolean) {
    setOpen(false)
    if (restoreFocus) triggerRef.current?.focus()
  }

  function choose(option: DropdownOption) {
    onChange(option.value)
    closeMenu(true)
  }

  // Foco inicial dentro do menu e posição correta antes de pintar.
  useLayoutEffect(() => {
    if (!open) return
    updatePosition()
    ;(searchable ? inputRef.current : listRef.current)?.focus()
  }, [open, searchable, updatePosition])

  // Rola a opção ativa para dentro da área visível.
  useEffect(() => {
    if (!open) return
    document.getElementById(`${baseId}-opt-${activeIndex}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [open, activeIndex, baseId, position])

  useEffect(() => {
    if (!open) return
    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node
      if (popoverRef.current?.contains(target) || triggerRef.current?.contains(target)) return
      setOpen(false)
    }
    function handleViewportChange() {
      updatePosition()
    }
    document.addEventListener('mousedown', handlePointerDown)
    window.addEventListener('resize', handleViewportChange)
    window.addEventListener('scroll', handleViewportChange, true)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      window.removeEventListener('resize', handleViewportChange)
      window.removeEventListener('scroll', handleViewportChange, true)
    }
  }, [open, updatePosition])

  function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      openMenu()
    }
  }

  function handlePopoverKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const lastIndex = visibleOptions.length - 1
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        setActiveIndex((index) => Math.min(lastIndex, index + 1))
        break
      case 'ArrowUp':
        event.preventDefault()
        setActiveIndex((index) => Math.max(0, index - 1))
        break
      case 'Home':
        event.preventDefault()
        setActiveIndex(0)
        break
      case 'End':
        event.preventDefault()
        setActiveIndex(Math.max(0, lastIndex))
        break
      case 'Enter': {
        event.preventDefault()
        const option = visibleOptions[activeIndex]
        if (option) choose(option)
        break
      }
      case 'Escape':
        event.preventDefault()
        event.stopPropagation()
        closeMenu(true)
        break
      case 'Tab':
        setOpen(false)
        break
    }
  }

  const activeDescendant =
    visibleOptions.length > 0 ? `${baseId}-opt-${activeIndex}` : undefined

  const trigger = (
      <button
        ref={triggerRef}
        type="button"
        className={`dropdown__trigger${className ? ` ${className}` : ''}`}
        data-active={isActive}
        data-open={open}
        data-variant={variant}
        data-empty={isField && !selected}
        aria-labelledby={isField ? `${labelId} ${textId}` : undefined}
        aria-invalid={errorMessage ? true : undefined}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        disabled={disabled}
        onClick={() => (open ? closeMenu(false) : openMenu())}
        onKeyDown={handleTriggerKeyDown}
      >
        {icon && <span className="dropdown__icon">{icon}</span>}
        <span className="dropdown__text" id={textId}>
          {isField ? (
            (selected?.label ?? placeholder)
          ) : (
            <>
              <span className="dropdown__label">{label}:</span> {selected?.label}
            </>
          )}
        </span>
        <ChevronDownIcon className="dropdown__chevron" />
      </button>
  )

  const popover = (
    <>

      {open &&
        position &&
        createPortal(
          // O contêiner só repassa o teclado ao menu; os elementos interativos são o campo de
          // busca e a lista (listbox).
          // eslint-disable-next-line jsx-a11y/no-static-element-interactions
          <div
            ref={popoverRef}
            className="dropdown__popover"
            style={{
              top: position.top,
              left: position.left,
              minWidth: position.minWidth,
              maxHeight: position.maxHeight,
            }}
            onKeyDown={handlePopoverKeyDown}
          >
            {searchable && (
              <div className="dropdown__search">
                <SearchIcon />
                <input
                  ref={inputRef}
                  type="text"
                  role="combobox"
                  aria-expanded="true"
                  aria-controls={listboxId}
                  aria-activedescendant={activeDescendant}
                  aria-label={`Buscar em ${label}`}
                  placeholder="Buscar…"
                  value={query}
                  onChange={(event) => {
                    setQuery(event.target.value)
                    setActiveIndex(0)
                  }}
                />
              </div>
            )}
            <ul
              ref={listRef}
              id={listboxId}
              className="dropdown__list"
              role="listbox"
              aria-label={label}
              tabIndex={searchable ? -1 : 0}
              aria-activedescendant={searchable ? undefined : activeDescendant}
            >
              {visibleOptions.map((option, index) => (
                <li
                  key={option.value}
                  id={`${baseId}-opt-${index}`}
                  role="option"
                  aria-selected={option.value === value}
                  data-active={index === activeIndex}
                  className="dropdown__option"
                  onMouseMove={() => setActiveIndex(index)}
                  onClick={() => choose(option)}
                >
                  <span className="dropdown__option-label">{option.label}</span>
                  {option.value === value && <CheckIcon className="dropdown__check" />}
                </li>
              ))}
              {visibleOptions.length === 0 && (
                <li className="dropdown__empty" role="presentation">
                  Nenhum resultado.
                </li>
              )}
            </ul>
          </div>,
          document.body,
        )}
    </>
  )

  if (!isField) {
    return (
      <>
        {trigger}
        {popover}
      </>
    )
  }
  return (
    <div className="dropdown-field">
      <span className="dropdown-field__label" id={labelId}>
        {label}
      </span>
      {trigger}
      {errorMessage && (
        <p role="alert" className="dropdown-field__error">
          {errorMessage}
        </p>
      )}
      {popover}
    </div>
  )
}
