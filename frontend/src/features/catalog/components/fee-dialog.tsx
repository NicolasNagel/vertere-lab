import { useQueryClient, type QueryKey } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { describeError } from '../../../shared/api/describe-error'
import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { Modal } from '../../../shared/ui/modal'
import { TextField } from '../../../shared/ui/text-field'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-row-popover.css'
import './fees.css'

interface FeeDialogProps {
  titleId: string
  title: string
  subtitle?: string
  /** Há alguma mudança válida para salvar? */
  canSave: boolean
  isPending: boolean
  error: unknown
  reason: string
  onReasonChange: (value: string) => void
  /** Cache a recarregar quando outra pessoa alterou o registro (409). */
  reloadKey: QueryKey
  onSave: () => void
  onClose: () => void
  children: ReactNode
}

/** Diálogo de cadastro/edição de taxa: campos, motivo obrigatório e Salvar/Cancelar. */
export function FeeDialog({
  titleId,
  title,
  subtitle,
  canSave,
  isPending,
  error,
  reason,
  onReasonChange,
  reloadKey,
  onSave,
  onClose,
  children,
}: FeeDialogProps) {
  const queryClient = useQueryClient()
  const message = describeError(error)
  const isConflict = error instanceof ApiError && error.status === 409

  return (
    <Modal
      size="md"
      className="attendance-popover"
      titleId={titleId}
      onClose={onClose}
      canDismiss={!isPending}
    >
      <aside className="attendance-row-popover" aria-label={title}>
        <header className="attendance-row-popover__header">
          <div className="attendance-row-popover__heading">
            <h2 id={titleId} className="attendance-row-popover__title">
              {title}
            </h2>
            {subtitle && <div className="attendance-row-popover__sub">{subtitle}</div>}
          </div>
          <div className="attendance-row-popover__actions">
            <button
              type="button"
              className="attendance-row-popover__close"
              aria-label="Fechar"
              disabled={isPending}
              onClick={onClose}
            >
              ×
            </button>
          </div>
        </header>
        <form
          className="attendance-row-popover__body fees__form"
          onSubmit={(event) => {
            event.preventDefault()
            if (canSave && reason.trim() && !isPending) onSave()
          }}
        >
          {children}
          <TextField
            id={`${titleId}-reason`}
            label="Motivo da alteração"
            disabled={isPending}
            value={reason}
            onChange={(event) => onReasonChange(event.target.value)}
          />
          {message && (
            <p role="alert" className="fees__error">
              {message}
            </p>
          )}
          <div className="fees__actions">
            <Button type="submit" disabled={isPending || !canSave || !reason.trim()}>
              {isPending ? 'Salvando…' : 'Salvar'}
            </Button>
            <Button type="button" variant="cancel" disabled={isPending} onClick={onClose}>
              Cancelar
            </Button>
            {isConflict && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => void queryClient.invalidateQueries({ queryKey: reloadKey })}
              >
                Recarregar
              </Button>
            )}
          </div>
        </form>
      </aside>
    </Modal>
  )
}
