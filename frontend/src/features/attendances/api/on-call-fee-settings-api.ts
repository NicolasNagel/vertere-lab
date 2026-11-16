import { throwIfNotOk } from '../../../shared/api/errors'
import {
  scheduleFromApi,
  scheduleToApi,
  type FeeScheduleValue,
} from '../../catalog/lib/fee-schedule'

const API_BASE = '/api/v1'

export type OnCallServiceLevel = 'PLANTAO_NORMAL' | 'PLANTAO_ESPECIAL'

export interface OnCallFeeSetting {
  id: string
  serviceLevel: OnCallServiceLevel
  feeAmount: string
  scheduleLabel: string
  schedule: FeeScheduleValue
  updatedAt: string
  rowVersion: number
}

interface ApiOnCallFeeSetting {
  id: string
  service_level: OnCallServiceLevel
  fee_amount: string
  schedule_label: string
  weekdays: number[]
  start_time: string | null
  end_time: string | null
  updated_at: string
  row_version: number
}

interface ApiOnCallFeeSettingListResponse {
  items: ApiOnCallFeeSetting[]
}

function fromApiOnCallFeeSetting(setting: ApiOnCallFeeSetting): OnCallFeeSetting {
  return {
    id: setting.id,
    serviceLevel: setting.service_level,
    feeAmount: setting.fee_amount,
    scheduleLabel: setting.schedule_label,
    schedule: scheduleFromApi(setting),
    updatedAt: setting.updated_at,
    rowVersion: setting.row_version,
  }
}

export async function fetchOnCallFeeSettings(): Promise<OnCallFeeSetting[]> {
  const response = await fetch(`${API_BASE}/on-call-fee-settings`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiOnCallFeeSettingListResponse
  return body.items.map(fromApiOnCallFeeSetting)
}

export interface OnCallFeeSettingUpdateInput {
  feeAmount: string
  schedule: FeeScheduleValue
  reason: string
  expectedRowVersion: number
}

export async function updateOnCallFeeSetting(
  serviceLevel: OnCallServiceLevel,
  input: OnCallFeeSettingUpdateInput,
): Promise<OnCallFeeSetting> {
  const response = await fetch(`${API_BASE}/on-call-fee-settings/${serviceLevel}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      fee_amount: input.feeAmount,
      ...scheduleToApi(input.schedule),
      reason: input.reason,
      expected_row_version: input.expectedRowVersion,
    }),
  })
  await throwIfNotOk(response)
  return fromApiOnCallFeeSetting((await response.json()) as ApiOnCallFeeSetting)
}
