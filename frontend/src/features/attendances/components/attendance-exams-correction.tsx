import { useMemo, useState } from 'react'

import { useActiveExamCategoriesQuery } from '../../catalog/api/use-active-exam-categories-query'
import { useAllActiveExamsQuery } from '../../catalog/api/use-all-active-exams-query'
import type { Exam } from '../../catalog/api/catalog-api'
import type { Patient } from '../../patients/api/patients-api'
import type { Attendance, AttendanceItemEditInput } from '../api/attendances-api'
import type { DraftExamSelection } from '../api/use-attendance-exam-selections'
import { useUpdateAttendanceItemsMutation } from '../api/use-update-attendance-items-mutation'
import { CorrectionFooter } from './attendance-correction-block'
import { ExamCartGrid } from './exam-cart-grid'

interface ExamsCorrectionFormProps {
  attendance: Attendance
  patient: Patient | undefined
  showMoney: boolean
  canDiscount: boolean
  onClose: () => void
}

function discountInput(value: string): string {
  return Number(value) > 0 ? value : ''
}

/** Corrige os exames de um atendimento já confirmado: marcar inclui (preço da data do
 * atendimento), desmarcar remove (fica no histórico), quantidade e desconto mudam na linha.
 * O backend recalcula o total; nada de valor é calculado aqui. */
export function ExamsCorrectionForm({
  attendance,
  patient,
  showMoney,
  canDiscount,
  onClose,
}: ExamsCorrectionFormProps) {
  const examsQuery = useAllActiveExamsQuery()
  const categoriesQuery = useActiveExamCategoriesQuery()
  const mutation = useUpdateAttendanceItemsMutation()
  const [reason, setReason] = useState('')

  const activeItems = useMemo(
    () => attendance.items.filter((item) => item.status === 'ACTIVE'),
    [attendance.items],
  )
  // Exame já lançado mostra o preço do snapshot (o que vale no atendimento), não o do catálogo.
  const exams = useMemo(
    () =>
      (examsQuery.data?.items ?? []).map((exam) => {
        const launched = activeItems.find((item) => item.examId === exam.id)
        return launched ? { ...exam, priceBase: launched.priceBase } : exam
      }),
    [examsQuery.data, activeItems],
  )
  const examById = useMemo(() => new Map(exams.map((exam) => [exam.id, exam])), [exams])

  // Exame inativo no catálogo não aparece na grade: a linha segue como está, sem edição.
  const lockedItems = activeItems.filter((item) => !examById.has(item.examId))

  const [edited, setEdited] = useState<DraftExamSelection[] | null>(null)
  const selections: DraftExamSelection[] =
    edited ??
    activeItems.flatMap((item) => {
      const exam = examById.get(item.examId)
      return exam
        ? [
            {
              exam,
              quantity: item.quantity,
              discountAmount: discountInput(item.discountAmount),
              overrideReason: item.overrideReason ?? '',
            },
          ]
        : []
    })

  function change(next: (current: DraftExamSelection[]) => DraftExamSelection[]) {
    setEdited(next(selections))
  }

  function toPayload(): AttendanceItemEditInput[] {
    const lines: AttendanceItemEditInput[] = lockedItems.map((item) => ({
      itemId: item.id,
      quantity: item.quantity,
      discountAmount: item.discountAmount,
      overrideReason: item.overrideReason,
    }))
    for (const selection of selections) {
      const existing = attendance.items.find((item) => item.examId === selection.exam.id)
      lines.push({
        itemId: existing?.id,
        examId: existing ? undefined : selection.exam.id,
        quantity: selection.quantity,
        discountAmount: selection.discountAmount || null,
        overrideReason: selection.overrideReason || null,
      })
    }
    return lines
  }

  const missingReason = selections.some(
    (selection) => Number(selection.discountAmount || 0) > 0 && !selection.overrideReason.trim(),
  )
  const unchanged = edited === null
  const canSave = !unchanged && selections.length + lockedItems.length > 0 && !missingReason

  return (
    <div className="attendance-correction-block__form">
      {lockedItems.length > 0 && (
        <p className="attendance-readonly-detail__hint">
          {lockedItems.map((item) => item.examName).join(', ')}: exame inativo no catálogo, mantido
          como está.
        </p>
      )}
      <ExamCartGrid
        exams={exams}
        categories={categoriesQuery.data ?? []}
        selections={selections}
        showMoney={showMoney}
        canDiscount={canDiscount}
        patientSpeciesId={patient?.speciesId ?? null}
        isLoading={examsQuery.isLoading || categoriesQuery.isLoading}
        isError={examsQuery.isError || categoriesQuery.isError}
        disabled={mutation.isPending}
        onAdd={(exam: Exam) =>
          change((current) => [
            ...current,
            { exam, quantity: 1, discountAmount: '', overrideReason: '' },
          ])
        }
        onRemove={(examId) =>
          change((current) => current.filter((selection) => selection.exam.id !== examId))
        }
        onUpdate={(examId, patch) =>
          change((current) =>
            current.map((selection) =>
              selection.exam.id === examId ? { ...selection, ...patch } : selection,
            ),
          )
        }
      />
      <CorrectionFooter
        attendanceId={attendance.id}
        reason={reason}
        onReasonChange={setReason}
        canSave={canSave}
        isPending={mutation.isPending}
        error={mutation.error}
        onSave={() =>
          mutation.mutate(
            {
              attendanceId: attendance.id,
              rowVersion: attendance.rowVersion,
              reason: reason.trim(),
              items: toPayload(),
            },
            { onSuccess: onClose },
          )
        }
        onCancel={onClose}
      />
    </div>
  )
}
