import { useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { ApiError } from '../../../shared/api/errors'
import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { useDebouncedValue } from '../../../shared/lib/use-debounced-value'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import { useAuth } from '../../auth/auth-context'
import type { Exam } from '../../catalog/api/catalog-api'
import { attendanceQueryKey } from '../api/use-attendance-query'
import { useAttendancePreviewQuery } from '../api/use-attendance-preview-query'
import { useConfirmAttendanceMutation } from '../api/use-confirm-attendance-mutation'
import type { Attendance, AttendanceConfirmItemInput } from '../api/attendances-api'
import { AttendanceHeaderDetails } from './attendance-header-details'
import { AttendanceSummaryPanel } from './attendance-summary-panel'
import { ExamPicker } from './exam-picker'
import './attendance-confirmation-form.css'

interface DraftExamSelection {
  exam: Exam
  quantity: number
  discountAmount: string
  overrideReason: string
}

function describeError(error: unknown): string | null {
  if (error === null || error === undefined) return null
  if (error instanceof ApiError) return error.message
  return 'Falha de conexão. Verifique sua internet e tente novamente.'
}

interface AttendanceConfirmationFormProps {
  attendance: Attendance
  onConfirmed: (attendance: Attendance) => void
}

export function AttendanceConfirmationForm({
  attendance,
  onConfirmed,
}: AttendanceConfirmationFormProps) {
  const { user } = useAuth()
  const canOverridePrice = user?.permissions.includes('attendances.override_price') ?? false
  const canEditHeader = user?.permissions.includes('attendances.update') ?? false
  const queryClient = useQueryClient()

  const [selections, setSelections] = useState<DraftExamSelection[]>([])
  const confirmMutation = useConfirmAttendanceMutation()

  const itemsForApi: AttendanceConfirmItemInput[] = useMemo(
    () =>
      selections.map((selection) => ({
        examId: selection.exam.id,
        quantity: selection.quantity,
        discountAmount: selection.discountAmount || null,
        overrideReason: selection.overrideReason || null,
      })),
    [selections],
  )
  const debouncedItems = useDebouncedValue(itemsForApi, 400)
  const previewQuery = useAttendancePreviewQuery(
    attendance.id,
    debouncedItems.length > 0 ? debouncedItems : null,
  )

  const hasMissingOverrideReason = selections.some(
    (selection) => Number(selection.discountAmount || 0) > 0 && !selection.overrideReason.trim(),
  )
  const canConfirm =
    selections.length > 0 && !hasMissingOverrideReason && !confirmMutation.isPending

  function addExam(exam: Exam) {
    setSelections((current) => [
      ...current,
      { exam, quantity: 1, discountAmount: '', overrideReason: '' },
    ])
  }

  function removeExam(examId: string) {
    setSelections((current) => current.filter((selection) => selection.exam.id !== examId))
  }

  function updateSelection(examId: string, patch: Partial<DraftExamSelection>) {
    setSelections((current) =>
      current.map((selection) =>
        selection.exam.id === examId ? { ...selection, ...patch } : selection,
      ),
    )
  }

  function handleConfirm() {
    const idempotencyKey = crypto.randomUUID()
    confirmMutation.mutate(
      { attendanceId: attendance.id, items: itemsForApi, idempotencyKey },
      { onSuccess: onConfirmed },
    )
  }

  function handleReload() {
    void queryClient.invalidateQueries({ queryKey: attendanceQueryKey(attendance.id) })
  }

  const errorMessage = describeError(confirmMutation.error)
  const isConflict = confirmMutation.error instanceof ApiError && confirmMutation.error.status === 409

  return (
    <div className="attendance-confirmation-form">
      <AttendanceHeaderDetails attendance={attendance} editable={canEditHeader} />

      <div className="attendance-confirmation-form__main">
        <section className="attendance-confirmation-form__section">
          <div className="attendance-confirmation-form__section-header">
            <h2 className="attendance-confirmation-form__section-title">Exames</h2>
            <span className="attendance-confirmation-form__count">
              {selections.length} selecionado{selections.length === 1 ? '' : 's'}
            </span>
          </div>

          {selections.length > 0 && (
            <ul className="attendance-confirmation-form__items" aria-label="Exames selecionados">
              {selections.map((selection) => (
                <li key={selection.exam.id} className="attendance-confirmation-form__item">
                  <div className="attendance-confirmation-form__item-main">
                    <span className="attendance-confirmation-form__item-name">
                      {selection.exam.name}
                    </span>
                    <span className="attendance-confirmation-form__item-price">
                      {selection.exam.priceBase
                        ? formatCurrencyBRL(selection.exam.priceBase)
                        : '—'}
                    </span>
                    <button
                      type="button"
                      className="attendance-confirmation-form__remove-button"
                      aria-label={`Remover ${selection.exam.name}`}
                      disabled={confirmMutation.isPending}
                      onClick={() => removeExam(selection.exam.id)}
                    >
                      ×
                    </button>
                  </div>
                  <div className="attendance-confirmation-form__item-fields">
                    <TextField
                      id={`quantity-${selection.exam.id}`}
                      label="Quantidade"
                      type="number"
                      min={1}
                      disabled={confirmMutation.isPending}
                      value={selection.quantity}
                      onChange={(event) =>
                        updateSelection(selection.exam.id, {
                          quantity: Math.max(1, Number(event.target.value) || 1),
                        })
                      }
                    />
                    {canOverridePrice && (
                      <>
                        <TextField
                          id={`discount-${selection.exam.id}`}
                          label="Desconto (R$)"
                          type="number"
                          min={0}
                          step="0.01"
                          disabled={confirmMutation.isPending}
                          value={selection.discountAmount}
                          onChange={(event) =>
                            updateSelection(selection.exam.id, {
                              discountAmount: event.target.value,
                            })
                          }
                        />
                        {Number(selection.discountAmount || 0) > 0 && (
                          <TextField
                            id={`override-reason-${selection.exam.id}`}
                            label="Motivo do desconto"
                            disabled={confirmMutation.isPending}
                            value={selection.overrideReason}
                            errorMessage={
                              !selection.overrideReason.trim()
                                ? 'Desconto exige motivo.'
                                : undefined
                            }
                            onChange={(event) =>
                              updateSelection(selection.exam.id, {
                                overrideReason: event.target.value,
                              })
                            }
                          />
                        )}
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}

          <ExamPicker
            disabled={confirmMutation.isPending}
            excludeExamIds={selections.map((selection) => selection.exam.id)}
            onSelect={addExam}
          />
        </section>
      </div>

      <div className="attendance-confirmation-form__side">
        <AttendanceSummaryPanel
          items={previewQuery.data?.items ?? []}
          subtotal={previewQuery.data?.subtotal ?? '0.00'}
          discountTotal={previewQuery.data?.discountTotal ?? '0.00'}
          surchargeTotal={previewQuery.data?.surchargeTotal ?? '0.00'}
          grandTotal={previewQuery.data?.grandTotal ?? '0.00'}
          isLoading={selections.length > 0 && previewQuery.isLoading}
        />

        {selections.length === 0 && (
          <p className="attendance-confirmation-form__hint">
            Selecione ao menos um exame para ver o valor.
          </p>
        )}

        {errorMessage && (
          <div className="attendance-confirmation-form__domain-error" role="alert">
            <p>{errorMessage}</p>
            {isConflict && (
              <button type="button" onClick={handleReload}>
                Recarregar atendimento
              </button>
            )}
          </div>
        )}

        <Button type="button" disabled={!canConfirm} onClick={handleConfirm}>
          {confirmMutation.isPending ? 'Confirmando…' : 'Confirmar atendimento'}
        </Button>
      </div>
    </div>
  )
}
