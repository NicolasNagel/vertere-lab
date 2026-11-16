import type { FeeAttendanceType } from '../../attendances/api/clinic-fee-rules-api'

export const FEE_ATTENDANCE_TYPES: {
  value: FeeAttendanceType
  label: string
}[] = [
  { value: 'ROTINA', label: 'Rotina' },
  { value: 'PLANTAO_NORMAL', label: 'Plantão normal' },
  { value: 'PLANTAO_ESPECIAL', label: 'Plantão especial' },
  { value: 'URGENTE', label: 'Urgente' },
]

const TYPE_LABEL = new Map(FEE_ATTENDANCE_TYPES.map((item) => [item.value, item.label]))

export function attendanceTypeLabel(type: FeeAttendanceType): string {
  return TYPE_LABEL.get(type) ?? type
}

interface RuleConditions {
  examIds: string[]
  attendanceTypes: FeeAttendanceType[]
}

/** Resumo curto das condições, ex.: "Hemograma +1 · Urgente ou Plantão normal". */
export function conditionsSummary(rule: RuleConditions, examNameById: Map<string, string>): string {
  const parts: string[] = []
  if (rule.examIds.length > 0) {
    const names = rule.examIds.map((id) => examNameById.get(id) ?? 'Exame')
    parts.push(names.length > 1 ? `${names[0]} +${names.length - 1}` : (names[0] ?? ''))
  }
  if (rule.attendanceTypes.length > 0) {
    parts.push(rule.attendanceTypes.map(attendanceTypeLabel).join(' ou '))
  }
  return parts.length > 0 ? parts.join(' · ') : 'Todos os atendimentos'
}
