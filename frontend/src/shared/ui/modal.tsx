import { useEffect, useRef, type ReactNode } from 'react'

import './modal.css'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

interface ModalProps {
  /** id do título; vira `aria-labelledby` do diálogo. */
  titleId: string
  onClose: () => void
  /** false enquanto há operação em andamento: Escape e clique fora não fecham. */
  canDismiss?: boolean
  /** Fecha ao clicar no fundo (padrão: não — evita perder formulário por clique acidental). */
  dismissOnBackdrop?: boolean
  size?: 'sm' | 'md' | 'lg'
  className?: string
  children: ReactNode
}

/** Diálogo modal acessível: Escape, foco preso, foco inicial e restauração do foco ao fechar. */
export function Modal({
  titleId,
  onClose,
  canDismiss = true,
  dismissOnBackdrop = false,
  size = 'md',
  className,
  children,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  const canDismissRef = useRef(canDismiss)
  onCloseRef.current = onClose
  canDismissRef.current = canDismiss

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const panel = panelRef.current
    if (panel && !panel.contains(document.activeElement)) {
      // Um filho pode ter focado um campo próprio (autofocus); só cai no primeiro focável se não.
      const first = panel.querySelector<HTMLElement>(FOCUSABLE)
      ;(first ?? panel).focus()
    }
    return () => {
      if (opener?.isConnected) opener.focus()
    }
  }, [])

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.stopPropagation()
      if (canDismissRef.current) onCloseRef.current()
      return
    }
    if (event.key !== 'Tab' || !panelRef.current) return
    const items = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE))
    const first = items[0]
    const last = items[items.length - 1]
    if (!first || !last) {
      event.preventDefault()
      return
    }
    const active = document.activeElement
    if (event.shiftKey && (active === first || active === panelRef.current)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && active === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <div
      className="modal__backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (dismissOnBackdrop && canDismiss && event.target === event.currentTarget) onClose()
      }}
      onKeyDown={handleKeyDown}
    >
      <div
        ref={panelRef}
        className={`modal modal--${size}${className ? ` ${className}` : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        {children}
      </div>
    </div>
  )
}
