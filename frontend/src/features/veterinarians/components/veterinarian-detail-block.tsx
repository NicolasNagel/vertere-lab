import { useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { describeError } from '../../../shared/api/describe-error'
import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import { veterinarianQueryKey } from '../api/use-veterinarian-query'
import '../../../shared/ui/button.css'
import '../../../shared/ui/readonly-detail.css'
import '../../../shared/ui/correction-block.css'

interface VeterinarianDetailBlockProps {
  title: string
  veterinarianId: string
  canEdit: boolean
  children: ReactNode
  form: (api: { close: () => void }) => ReactNode
}

/** Bloco do detalhe do veterinário: leitura à vista; "Editar" troca pelo formulário do bloco. */
export function VeterinarianDetailBlock({
  title,
  veterinarianId,
  canEdit,
  children,
  form,
}: VeterinarianDetailBlockProps) {
  const [editing, setEditing] = useState(false)
  const headingId = `veterinarian-block-${veterinarianId}-${title}`

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

interface VeterinarianReasonFieldProps {
  veterinarianId: string
  reason: string
  onReasonChange: (value: string) => void
  disabled: boolean
}

/** Campo de motivo (obrigatório) de qualquer alteração. */
export function VeterinarianReasonField({
  veterinarianId,
  reason,
  onReasonChange,
  disabled,
}: VeterinarianReasonFieldProps) {
  return (
    <TextField
      id={`veterinarian-reason-${veterinarianId}`}
      label="Motivo da alteração"
      disabled={disabled}
      value={reason}
      onChange={(event) => onReasonChange(event.target.value)}
    />
  )
}

interface VeterinarianErrorProps {
  veterinarianId: string
  error: unknown
}

/** Mensagem do erro e, em conflito de versão, a opção de recarregar (nunca sobrescreve). */
export function VeterinarianDetailError({ veterinarianId, error }: VeterinarianErrorProps) {
  const queryClient = useQueryClient()
  const message = describeError(error)
  if (!message) return null
  const isConflict = error instanceof ApiError && error.status === 409
  return (
    <>
      <p className="attendance-correction-block__error" role="alert">
        {message}
      </p>
      {isConflict && (
        <div className="attendance-correction-block__actions">
          <Button
            type="button"
            variant="ghost"
            onClick={() =>
              void queryClient.invalidateQueries({
                queryKey: veterinarianQueryKey(veterinarianId),
              })
            }
          >
            Recarregar veterinário
          </Button>
        </div>
      )}
    </>
  )
}

interface VeterinarianDetailFooterProps {
  veterinarianId: string
  reason: string
  onReasonChange: (value: string) => void
  canSave: boolean
  isPending: boolean
  error: unknown
  onSave: () => void
  onCancel: () => void
}

/** Motivo (obrigatório) + Salvar/Cancelar. */
export function VeterinarianDetailFooter({
  veterinarianId,
  reason,
  onReasonChange,
  canSave,
  isPending,
  error,
  onSave,
  onCancel,
}: VeterinarianDetailFooterProps) {
  return (
    <div className="attendance-correction-block__footer">
      <VeterinarianReasonField
        veterinarianId={veterinarianId}
        reason={reason}
        onReasonChange={onReasonChange}
        disabled={isPending}
      />
      <VeterinarianDetailError veterinarianId={veterinarianId} error={error} />
      <div className="attendance-correction-block__actions">
        <Button type="button" disabled={isPending || !canSave || !reason.trim()} onClick={onSave}>
          {isPending ? 'Salvando…' : 'Salvar'}
        </Button>
        <Button type="button" variant="cancel" disabled={isPending} onClick={onCancel}>
          Cancelar
        </Button>
      </div>
    </div>
  )
}
