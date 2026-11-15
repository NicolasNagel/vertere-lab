import { useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { describeError } from '../../../shared/api/describe-error'
import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import { examQueryKey } from '../api/use-exam-query'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-readonly-detail.css'
import '../../attendances/components/attendance-correction-block.css'

interface ExamDetailBlockProps {
  title: string
  examId: string
  canEdit: boolean
  children: ReactNode
  form: (api: { close: () => void }) => ReactNode
}

/** Bloco do detalhe do exame: leitura à vista; "Editar" troca pelo formulário do bloco. */
export function ExamDetailBlock({ title, examId, canEdit, children, form }: ExamDetailBlockProps) {
  const [editing, setEditing] = useState(false)
  const headingId = `exam-block-${examId}-${title}`

  return (
    <section className="attendance-readonly-detail__section" aria-labelledby={headingId}>
      <div className="attendance-correction-block__header">
        <h2 id={headingId} className="attendance-readonly-detail__section-title">
          {title}
        </h2>
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
      {editing ? form({ close: () => setEditing(false) }) : children}
    </section>
  )
}

interface ExamDetailFooterProps {
  examId: string
  reason: string
  onReasonChange: (value: string) => void
  canSave: boolean
  isPending: boolean
  error: unknown
  onSave: () => void
  onCancel: () => void
}

/** Motivo (obrigatório) + Salvar/Cancelar; conflito de versão oferece recarregar. */
export function ExamDetailFooter({
  examId,
  reason,
  onReasonChange,
  canSave,
  isPending,
  error,
  onSave,
  onCancel,
}: ExamDetailFooterProps) {
  const queryClient = useQueryClient()
  const message = describeError(error)
  const isConflict = error instanceof ApiError && error.status === 409

  return (
    <div className="attendance-correction-block__footer">
      <TextField
        id={`exam-reason-${examId}`}
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
              void queryClient.invalidateQueries({
                queryKey: examQueryKey(examId),
              })
            }
          >
            Recarregar exame
          </Button>
        )}
      </div>
    </div>
  )
}
