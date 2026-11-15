import { useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { describeError } from '../../../shared/api/describe-error'
import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import { attendanceQueryKey } from '../api/use-attendance-query'
import '../../../shared/ui/button.css'
import './attendance-correction-block.css'

interface CorrectionFormApi {
  close: () => void
}

interface AttendanceCorrectionBlockProps {
  title: string
  attendanceId: string
  /** Quem pode corrigir; o backend decide de verdade. */
  canEdit: boolean
  /** Ações extras ao lado do "Editar" (ex.: corrigir o cadastro do paciente). */
  actions?: ReactNode
  children: ReactNode
  form: (api: CorrectionFormApi) => ReactNode
}

/** Bloco do detalhe com "Editar" sempre disponível: o conteúdo normal fica à vista e, ao
 * editar, o formulário do bloco o substitui. Todo bloco corrige com motivo obrigatório. */
export function AttendanceCorrectionBlock({
  title,
  attendanceId,
  canEdit,
  actions,
  children,
  form,
}: AttendanceCorrectionBlockProps) {
  const [editing, setEditing] = useState(false)
  const headingId = `correction-${attendanceId}-${title}`

  return (
    <section className="attendance-readonly-detail__section" aria-labelledby={headingId}>
      <div className="attendance-correction-block__header">
        <h2 id={headingId} className="attendance-readonly-detail__section-title">
          {title}
        </h2>
        <div className="attendance-correction-block__buttons">
          {actions}
          {canEdit && !editing && (
            <button
              type="button"
              className="button button--secondary attendance-correction-block__edit"
              aria-label={`Editar ${title.toLowerCase()}`}
              onClick={() => setEditing(true)}
            >
              Editar
            </button>
          )}
        </div>
      </div>
      {editing ? form({ close: () => setEditing(false) }) : children}
    </section>
  )
}

interface CorrectionFooterProps {
  attendanceId: string
  reason: string
  onReasonChange: (value: string) => void
  /** Há algo diferente do que está salvo? */
  canSave: boolean
  isPending: boolean
  error: unknown
  onSave: () => void
  onCancel: () => void
}

/** Motivo + Salvar/Cancelar de qualquer correção; conflito de versão oferece recarregar. */
export function CorrectionFooter({
  attendanceId,
  reason,
  onReasonChange,
  canSave,
  isPending,
  error,
  onSave,
  onCancel,
}: CorrectionFooterProps) {
  const queryClient = useQueryClient()
  const message = describeError(error)
  const isConflict = error instanceof ApiError && error.status === 409

  return (
    <div className="attendance-correction-block__footer">
      <TextField
        id={`correction-reason-${attendanceId}`}
        label="Motivo da alteração"
        disabled={isPending}
        value={reason}
        onChange={(event) => onReasonChange(event.target.value)}
      />
      {message && (
        <p className="attendance-correction-block__error" role="alert">
          {message}
        </p>
      )}
      <div className="attendance-correction-block__actions">
        <Button type="button" disabled={isPending || !canSave || !reason.trim()} onClick={onSave}>
          {isPending ? 'Salvando…' : 'Salvar'}
        </Button>
        <Button type="button" variant="cancel" disabled={isPending} onClick={onCancel}>
          Cancelar
        </Button>
        {isConflict && (
          <Button
            type="button"
            variant="ghost"
            onClick={() =>
              void queryClient.invalidateQueries({ queryKey: attendanceQueryKey(attendanceId) })
            }
          >
            Recarregar atendimento
          </Button>
        )}
      </div>
    </div>
  )
}
