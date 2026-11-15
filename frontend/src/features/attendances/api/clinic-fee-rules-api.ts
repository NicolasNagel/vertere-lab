import { apiRequest } from '../../../shared/api/http-client'

export interface ClinicFeeRule {
  id: string
  clinicId: string
  name: string
  feeAmount: string
  validFrom: string
  validTo: string | null
  isActive: boolean
  /** Condições: vazio = qualquer exame / qualquer tipo de atendimento. */
  examIds: string[]
  attendanceTypes: FeeAttendanceType[]
  updatedAt: string
  rowVersion: number
}

export type FeeAttendanceType = 'ROTINA' | 'PLANTAO_NORMAL' | 'PLANTAO_ESPECIAL' | 'URGENTE'

interface ApiClinicFeeRule {
  id: string
  clinic_id: string
  name: string
  fee_amount: string
  valid_from: string
  valid_to: string | null
  is_active: boolean
  exam_ids: string[]
  attendance_types: FeeAttendanceType[]
  updated_at: string
  row_version: number
}

function fromApi(rule: ApiClinicFeeRule): ClinicFeeRule {
  return {
    id: rule.id,
    clinicId: rule.clinic_id,
    name: rule.name,
    feeAmount: rule.fee_amount,
    validFrom: rule.valid_from,
    validTo: rule.valid_to,
    isActive: rule.is_active,
    examIds: rule.exam_ids,
    attendanceTypes: rule.attendance_types,
    updatedAt: rule.updated_at,
    rowVersion: rule.row_version,
  }
}

export async function fetchClinicFeeRules(clinicId?: string): Promise<ClinicFeeRule[]> {
  const query = clinicId ? `?clinic_id=${encodeURIComponent(clinicId)}` : ''
  const body = await apiRequest<{ items: ApiClinicFeeRule[] }>(`/clinic-fee-rules${query}`)
  return body.items.map(fromApi)
}

export interface ClinicFeeRuleValues {
  name: string
  feeAmount: string
  validFrom: string
  validTo: string | null
  examIds: string[]
  attendanceTypes: FeeAttendanceType[]
  reason: string
}

export async function createClinicFeeRule(
  input: ClinicFeeRuleValues & { clinicId: string; idempotencyKey: string },
): Promise<ClinicFeeRule> {
  return fromApi(
    await apiRequest<ApiClinicFeeRule>('/clinic-fee-rules', {
      method: 'POST',
      headers: { 'Idempotency-Key': input.idempotencyKey },
      body: {
        clinic_id: input.clinicId,
        name: input.name,
        fee_amount: input.feeAmount,
        valid_from: input.validFrom,
        valid_to: input.validTo,
        exam_ids: input.examIds,
        attendance_types: input.attendanceTypes,
        reason: input.reason,
      },
    }),
  )
}

export async function updateClinicFeeRule(
  id: string,
  input: ClinicFeeRuleValues & {
    isActive: boolean
    expectedRowVersion: number
  },
): Promise<ClinicFeeRule> {
  return fromApi(
    await apiRequest<ApiClinicFeeRule>(`/clinic-fee-rules/${id}`, {
      method: 'PATCH',
      body: {
        name: input.name,
        fee_amount: input.feeAmount,
        valid_from: input.validFrom,
        valid_to: input.validTo,
        is_active: input.isActive,
        exam_ids: input.examIds,
        attendance_types: input.attendanceTypes,
        reason: input.reason,
        expected_row_version: input.expectedRowVersion,
      },
    }),
  )
}
