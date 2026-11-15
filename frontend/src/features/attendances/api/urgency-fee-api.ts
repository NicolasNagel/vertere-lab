import { apiRequest } from '../../../shared/api/http-client'
import {
  scheduleFromApi,
  scheduleToApi,
  type FeeScheduleValue,
} from '../../catalog/lib/fee-schedule'

export interface UrgencyFeeSetting {
  id: string
  feeAmount: string
  scheduleLabel: string
  schedule: FeeScheduleValue
  updatedAt: string
  rowVersion: number
}

interface ApiUrgencyFeeSetting {
  id: string
  fee_amount: string
  schedule_label: string
  weekdays: number[]
  start_time: string | null
  end_time: string | null
  updated_at: string
  row_version: number
}

function fromApi(setting: ApiUrgencyFeeSetting): UrgencyFeeSetting {
  return {
    id: setting.id,
    feeAmount: setting.fee_amount,
    scheduleLabel: setting.schedule_label,
    schedule: scheduleFromApi(setting),
    updatedAt: setting.updated_at,
    rowVersion: setting.row_version,
  }
}

export async function fetchUrgencyFee(): Promise<UrgencyFeeSetting> {
  return fromApi(await apiRequest<ApiUrgencyFeeSetting>('/urgency-fee-setting'))
}

export interface UrgencyFeeUpdateInput {
  feeAmount: string
  schedule: FeeScheduleValue
  reason: string
  expectedRowVersion: number
}

export async function updateUrgencyFee(input: UrgencyFeeUpdateInput): Promise<UrgencyFeeSetting> {
  return fromApi(
    await apiRequest<ApiUrgencyFeeSetting>('/urgency-fee-setting', {
      method: 'PATCH',
      body: {
        fee_amount: input.feeAmount,
        ...scheduleToApi(input.schedule),
        reason: input.reason,
        expected_row_version: input.expectedRowVersion,
      },
    }),
  )
}
