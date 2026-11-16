import { apiRequest } from '../../../shared/api/http-client'

export interface UrgencyFeeSetting {
  id: string
  feeAmount: string
  updatedAt: string
  rowVersion: number
}

interface ApiUrgencyFeeSetting {
  id: string
  fee_amount: string
  updated_at: string
  row_version: number
}

function fromApi(setting: ApiUrgencyFeeSetting): UrgencyFeeSetting {
  return {
    id: setting.id,
    feeAmount: setting.fee_amount,
    updatedAt: setting.updated_at,
    rowVersion: setting.row_version,
  }
}

export async function fetchUrgencyFee(): Promise<UrgencyFeeSetting> {
  return fromApi(await apiRequest<ApiUrgencyFeeSetting>('/urgency-fee-setting'))
}

export interface UrgencyFeeUpdateInput {
  feeAmount: string
  reason: string
  expectedRowVersion: number
}

export async function updateUrgencyFee(input: UrgencyFeeUpdateInput): Promise<UrgencyFeeSetting> {
  return fromApi(
    await apiRequest<ApiUrgencyFeeSetting>('/urgency-fee-setting', {
      method: 'PATCH',
      body: {
        fee_amount: input.feeAmount,
        reason: input.reason,
        expected_row_version: input.expectedRowVersion,
      },
    }),
  )
}
