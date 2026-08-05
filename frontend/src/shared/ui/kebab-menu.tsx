import type { ReactNode } from 'react'
import { useEffect, useRef, useState } from 'react'

import './kebab-menu.css'

export interface KebabMenuItem {
  label: string
  onSelect: () => void
  destructive?: boolean
}

interface KebabMenuProps {
  items: KebabMenuItem[]
  label: string
  trigger?: ReactNode
  triggerClassName?: string
}

// Menu mínimo, controlado localmente — só existe para agrupar ações
// secundárias já especificadas (ex.: "Inativar"), não para introduzir ações
// não previstas na spec da tela. `trigger`/`triggerClassName` permitem reusar
// o mesmo menu como botão de cabeçalho (ex.: "Convidar usuário" + "Novo
// perfil"), não só como o ⋮ padrão.
export function KebabMenu({ items, label, trigger, triggerClassName }: KebabMenuProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return

    function handlePointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  return (
    <div className="kebab-menu" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        className={triggerClassName ?? 'kebab-menu__trigger'}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={label}
        onClick={() => setOpen((current) => !current)}
      >
        {trigger ?? '⋮'}
      </button>
      {open && (
        <ul className="kebab-menu__list" role="menu">
          {items.map((item) => (
            <li key={item.label} role="none">
              <button
                type="button"
                role="menuitem"
                className="kebab-menu__item"
                data-destructive={item.destructive}
                onClick={() => {
                  setOpen(false)
                  item.onSelect()
                }}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
