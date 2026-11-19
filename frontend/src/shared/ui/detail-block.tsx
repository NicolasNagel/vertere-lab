import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

import { describeError } from '../api/describe-error'
import { ApiError } from '../api/errors'
import { Button } from './button'
import { TextField } from './text-field'
import './button.css'
// Os estilos do bloco são os do detalhe/correção de atendimento, que Veterinários também usa.
import '../../features/attendances/components/attendance-readonly-detail.css'
import '../../features/attendances/components/attendance-correction-block.css'

interface DetailBlockProps {
  title: string
  canEdit: boolean
  children: ReactNode
  /** Formulário do bloco; `close` volta à leitura. */
  form: (api: { close: () => void }) => ReactNode
}

/** Bloco de detalhe: leitura à vista; "Editar" troca pelo formulário do próprio bloco. */
export function DetailBlock({ title, canEdit, children, form }: DetailBlockProps) {
  const [editing, setEditing] = useState(false)
  const headingId = useId()
  const editButtonRef = useRef<HTMLButtonElement>(null)
  const formRef = useRef<HTMLDivElement>(null)
  const wasEditing = useRef(false)
  // Perder a permissão (ex.: o paciente foi inativado) com o editor aberto volta à leitura.
  const showForm = editing && canEdit

  useEffect(() => {
    if (!canEdit) setEditing(false)
  }, [canEdit])

  // Teclado: ao abrir o editor o foco vai ao primeiro campo; ao fechar, volta ao botão "Editar".
  useEffect(() => {
    if (showForm) {
      formRef.current?.querySelector<HTMLElement>('input, select, textarea, button')?.focus()
    } else if (wasEditing.current) {
      editButtonRef.current?.focus()
    }
    wasEditing.current = showForm
  }, [showForm])

  return (
    <section className="attendance-readonly-detail__section" aria-labelledby={headingId}>
      <div className="attendance-correction-block__header">
        <h2 id={headingId} className="attendance-readonly-detail__section-title">
          {title}
        </h2>
        {canEdit && !showForm && (
          <button
            ref={editButtonRef}
            type="button"
            className="button button--secondary attendance-correction-block__edit"
            aria-label={`Editar ${title.toLowerCase()}`}
            onClick={() => setEditing(true)}
          >
            Editar
          </button>
        )}
      </div>
      {showForm ? <div ref={formRef}>{form({ close: () => setEditing(false) })}</div> : children}
    </section>
  )
}

interface BlockErrorProps {
  error: unknown
  /** Em conflito de versão (409) oferece recarregar; nunca sobrescreve em silêncio. */
  onReload?: () => void
  reloadLabel?: string
}

export function BlockError({ error, onReload, reloadLabel = 'Recarregar' }: BlockErrorProps) {
  const message = describeError(error)
  if (!message) return null
  const isConflict = error instanceof ApiError && error.status === 409
  return (
    <>
      <p className="attendance-correction-block__error" role="alert">
        {message}
      </p>
      {isConflict && onReload && (
        <div className="attendance-correction-block__actions">
          <Button type="button" variant="ghost" onClick={onReload}>
            {reloadLabel}
          </Button>
        </div>
      )}
    </>
  )
}

interface BlockFooterProps {
  /** Quando informado, mostra o campo de motivo (obrigatório se `reasonRequired`). */
  reasonLabel?: string
  reason?: string
  onReasonChange?: (value: string) => void
  reasonRequired?: boolean
  reasonError?: string
  canSave: boolean
  isPending: boolean
  error: unknown
  onReload?: () => void
  reloadLabel?: string
  onSave: () => void
  onCancel: () => void
}

/** Salvar/Cancelar do bloco, com motivo opcional e o erro da gravação. */
export function BlockFooter({
  reasonLabel,
  reason = '',
  onReasonChange,
  reasonRequired = false,
  reasonError,
  canSave,
  isPending,
  error,
  onReload,
  reloadLabel,
  onSave,
  onCancel,
}: BlockFooterProps) {
  const reasonId = useId()
  const missingReason = reasonRequired && !reason.trim()
  return (
    <div className="attendance-correction-block__footer">
      {reasonLabel && onReasonChange && (
        <TextField
          id={reasonId}
          label={reasonLabel}
          disabled={isPending}
          value={reason}
          errorMessage={reasonError}
          onChange={(event) => onReasonChange(event.target.value)}
        />
      )}
      <BlockError error={error} onReload={onReload} reloadLabel={reloadLabel} />
      <div className="attendance-correction-block__actions">
        <Button type="button" disabled={isPending || !canSave || missingReason} onClick={onSave}>
          {isPending ? 'Salvando…' : 'Salvar'}
        </Button>
        <Button type="button" variant="cancel" disabled={isPending} onClick={onCancel}>
          Cancelar
        </Button>
      </div>
    </div>
  )
}
