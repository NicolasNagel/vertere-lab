import { apiRequest } from '../../../shared/api/http-client'

export interface UrgencyFeeSetting {
  id: string
  feeAmount: string
  scheduleLabel: string
  updatedAt: string
  rowVersion: number
}

interface ApiUrgencyFeeSetting {
  id: string
  fee_amount: string
  schedule_label: string
  updated_at: string
  row_version: number
}

function fromApi(setting: ApiUrgencyFeeSetting): UrgencyFeeSetting {
  return {
    id: setting.id,
    feeAmount: setting.fee_amount,
    scheduleLabel: setting.schedule_label,
    updatedAt: setting.updated_at,
    rowVersion: setting.row_version,
  }
}

export async function fetchUrgencyFee(): Promise<UrgencyFeeSetting> {
  return fromApi(await apiRequest<ApiUrgencyFeeSetting>('/urgency-fee-setting'))
}

export interface UrgencyFeeUpdateInput {
  feeAmount: string
  scheduleLabel: string
  reason: string
  expectedRowVersion: number
}

export async function updateUrgencyFee(input: UrgencyFeeUpdateInput): Promise<UrgencyFeeSetting> {
  return fromApi(
    await apiRequest<ApiUrgencyFeeSetting>('/urgency-fee-setting', {
      method: 'PATCH',
      body: {
        fee_amount: input.feeAmount,
        schedule_label: input.scheduleLabel,
        reason: input.reason,
        expected_row_version: input.expectedRowVersion,
      },
    }),
  )
}
