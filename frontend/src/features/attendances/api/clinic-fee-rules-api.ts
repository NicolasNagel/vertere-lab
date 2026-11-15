import { apiRequest } from '../../../shared/api/http-client'

export interface ClinicFeeRule {
  id: string
  clinicId: string
  name: string
  feeAmount: string
  validFrom: string
  validTo: string | null
  isActive: boolean
  updatedAt: string
  rowVersion: number
}

interface ApiClinicFeeRule {
  id: string
  clinic_id: string
  name: string
  fee_amount: string
  valid_from: string
  valid_to: string | null
  is_active: boolean
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
  reason: string
}

export async function createClinicFeeRule(
  input: ClinicFeeRuleValues & { clinicId: string },
): Promise<ClinicFeeRule> {
  return fromApi(
    await apiRequest<ApiClinicFeeRule>('/clinic-fee-rules', {
      method: 'POST',
      body: {
        clinic_id: input.clinicId,
        name: input.name,
        fee_amount: input.feeAmount,
        valid_from: input.validFrom,
        valid_to: input.validTo,
        reason: input.reason,
      },
    }),
  )
}

export async function updateClinicFeeRule(
  id: string,
  input: ClinicFeeRuleValues & { isActive: boolean; expectedRowVersion: number },
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
        reason: input.reason,
        expected_row_version: input.expectedRowVersion,
      },
    }),
  )
}
