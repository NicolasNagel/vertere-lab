import { useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { ApiError } from '../../../shared/api/errors'
import { useDebouncedValue } from '../../../shared/lib/use-debounced-value'
import type { Exam } from '../../catalog/api/catalog-api'
import { attendanceQueryKey } from './use-attendance-query'
import { useAttendancePreviewQuery } from './use-attendance-preview-query'
import { useConfirmAttendanceMutation } from './use-confirm-attendance-mutation'
import type { Attendance, AttendanceConfirmItemInput } from './attendances-api'

export interface DraftExamSelection {
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

/** Estado de seleção de exames + prévia de preço + confirmação — extraído
 * de `AttendanceConfirmationForm` para ser reaproveitado também pela tela
 * de abertura de protocolo unificada, sem duplicar a lógica de
 * preço/idempotência/conflito de versão. */
export function useAttendanceExamSelections(attendance: Attendance | null, onConfirmed: (attendance: Attendance) => void) {
  const queryClient = useQueryClient()
  const [selections, setSelections] = useState<DraftExamSelection[]>([])
  const submissionStarted = useRef(false)
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
    attendance?.id ?? null,
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
    if (!attendance || !canConfirm || submissionStarted.current) return
    submissionStarted.current = true
    const idempotencyKey = crypto.randomUUID()
    confirmMutation.mutate(
      { attendanceId: attendance.id, items: itemsForApi, idempotencyKey },
      {
        onSuccess: onConfirmed,
        onError: () => {
          submissionStarted.current = false
        },
      },
    )
  }

  function handleReload() {
    if (!attendance) return
    void queryClient.invalidateQueries({ queryKey: attendanceQueryKey(attendance.id) })
  }

  const errorMessage = describeError(confirmMutation.error)
  const isConflict = confirmMutation.error instanceof ApiError && confirmMutation.error.status === 409

  return {
    selections,
    previewQuery,
    canConfirm,
    isPending: confirmMutation.isPending,
    errorMessage,
    isConflict,
    addExam,
    removeExam,
    updateSelection,
    handleConfirm,
    handleReload,
  }
}
