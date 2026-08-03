import { throwIfNotOk } from '../../../shared/api/errors'

const API_BASE = '/api/v1'

export interface ClosurePreviewItem {
  attendanceId: string
  attendanceExamId: string
  protocolNumber: string | null
  patientName: string
  examName: string
  totalAmount: string
}

export interface ClosurePreviewBlockedItem extends ClosurePreviewItem {
  reason: string
}

export interface ClosurePreview {
  clinicId: string
  competenceYear: number
  competenceMonth: number
  periodStart: string
  periodEnd: string
  attendanceCount: number
  cancelledAttendanceCount: number
  itemCount: number
  subtotal: string
  discountTotal: string
  surchargeTotal: string
  onCallFeeTotal: string
  grandTotal: string
  eligibleItems: ClosurePreviewItem[]
  blockedItems: ClosurePreviewBlockedItem[]
  generatedAt: string
}

export interface ClosurePreviewParams {
  clinicId: string
  year: number
  month: number
}

interface ApiClosurePreviewItem {
  attendance_id: string
  attendance_exam_id: string
  protocol_number: string | null
  patient_name: string
  exam_name: string
  total_amount: string
}

interface ApiClosurePreviewBlockedItem extends ApiClosurePreviewItem {
  reason: string
}

interface ApiClosurePreview {
  clinic_id: string
  competence_year: number
  competence_month: number
  period_start: string
  period_end: string
  attendance_count: number
  cancelled_attendance_count: number
  item_count: number
  subtotal: string
  discount_total: string
  surcharge_total: string
  on_call_fee_total: string
  grand_total: string
  eligible_items: ApiClosurePreviewItem[]
  blocked_items: ApiClosurePreviewBlockedItem[]
  generated_at: string
}

function fromApiItem(item: ApiClosurePreviewItem): ClosurePreviewItem {
  return {
    attendanceId: item.attendance_id,
    attendanceExamId: item.attendance_exam_id,
    protocolNumber: item.protocol_number,
    patientName: item.patient_name,
    examName: item.exam_name,
    totalAmount: item.total_amount,
  }
}

function fromApiBlockedItem(item: ApiClosurePreviewBlockedItem): ClosurePreviewBlockedItem {
  return { ...fromApiItem(item), reason: item.reason }
}

function fromApiClosurePreview(preview: ApiClosurePreview): ClosurePreview {
  return {
    clinicId: preview.clinic_id,
    competenceYear: preview.competence_year,
    competenceMonth: preview.competence_month,
    periodStart: preview.period_start,
    periodEnd: preview.period_end,
    attendanceCount: preview.attendance_count,
    cancelledAttendanceCount: preview.cancelled_attendance_count,
    itemCount: preview.item_count,
    subtotal: preview.subtotal,
    discountTotal: preview.discount_total,
    surchargeTotal: preview.surcharge_total,
    onCallFeeTotal: preview.on_call_fee_total,
    grandTotal: preview.grand_total,
    eligibleItems: preview.eligible_items.map(fromApiItem),
    blockedItems: preview.blocked_items.map(fromApiBlockedItem),
    generatedAt: preview.generated_at,
  }
}

export async function fetchClosurePreview(params: ClosurePreviewParams): Promise<ClosurePreview> {
  const query = new URLSearchParams({
    clinic_id: params.clinicId,
    year: String(params.year),
    month: String(params.month),
  })
  const response = await fetch(`${API_BASE}/closures/preview?${query.toString()}`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  return fromApiClosurePreview((await response.json()) as ApiClosurePreview)
}

export type MonthlyClosureStatus = 'CLOSED' | 'REOPENED'

export interface MonthlyClosureItem {
  id: string
  attendanceId: string
  attendanceExamId: string
  protocolNumber: string | null
  patientName: string
  examName: string
  priceBase: string
  quantity: number
  discountAmount: string
  surchargeAmount: string
  totalAmount: string
}

export type FinancialAdjustmentKind = 'CREDIT' | 'DEBIT'

export interface FinancialAdjustment {
  id: string
  monthlyClosureId: string
  monthlyClosureItemId: string | null
  kind: FinancialAdjustmentKind
  amount: string
  reason: string
  createdBy: string | null
  createdAt: string
}

export interface MonthlyClosure {
  id: string
  clinicId: string
  competenceYear: number
  competenceMonth: number
  periodStart: string
  periodEnd: string
  status: MonthlyClosureStatus
  itemCount: number
  subtotal: string
  discountTotal: string
  surchargeTotal: string
  onCallFeeTotal: string
  grandTotal: string
  generatedBy: string | null
  closedBy: string | null
  generatedAt: string
  closedAt: string
  reopenedAt: string | null
  version: number
  items: MonthlyClosureItem[]
  adjustments: FinancialAdjustment[]
}

export interface MonthlyClosureSummary {
  id: string
  clinicId: string
  competenceYear: number
  competenceMonth: number
  periodStart: string
  periodEnd: string
  status: MonthlyClosureStatus
  itemCount: number
  grandTotal: string
  closedBy: string | null
  closedAt: string
  version: number
}

export interface MonthlyClosurePage {
  items: MonthlyClosureSummary[]
  total: number
  page: number
  pageSize: number
}

interface ApiMonthlyClosureItem {
  id: string
  attendance_id: string
  attendance_exam_id: string
  protocol_number: string | null
  patient_name: string
  exam_name: string
  price_base: string
  quantity: number
  discount_amount: string
  surcharge_amount: string
  total_amount: string
}

interface ApiMonthlyClosure {
  id: string
  clinic_id: string
  competence_year: number
  competence_month: number
  period_start: string
  period_end: string
  status: MonthlyClosureStatus
  item_count: number
  subtotal: string
  discount_total: string
  surcharge_total: string
  on_call_fee_total: string
  grand_total: string
  generated_by: string | null
  closed_by: string | null
  generated_at: string
  closed_at: string
  reopened_at: string | null
  version: number
  items: ApiMonthlyClosureItem[]
  adjustments: ApiFinancialAdjustment[]
}

interface ApiFinancialAdjustment {
  id: string
  monthly_closure_id: string
  monthly_closure_item_id: string | null
  kind: FinancialAdjustmentKind
  amount: string
  reason: string
  created_by: string | null
  created_at: string
}

interface ApiMonthlyClosureSummary {
  id: string
  clinic_id: string
  competence_year: number
  competence_month: number
  period_start: string
  period_end: string
  status: MonthlyClosureStatus
  item_count: number
  grand_total: string
  closed_by: string | null
  closed_at: string
  version: number
}

interface ApiMonthlyClosurePage {
  items: ApiMonthlyClosureSummary[]
  total: number
  page: number
  page_size: number
}

function fromApiMonthlyClosureItem(item: ApiMonthlyClosureItem): MonthlyClosureItem {
  return {
    id: item.id,
    attendanceId: item.attendance_id,
    attendanceExamId: item.attendance_exam_id,
    protocolNumber: item.protocol_number,
    patientName: item.patient_name,
    examName: item.exam_name,
    priceBase: item.price_base,
    quantity: item.quantity,
    discountAmount: item.discount_amount,
    surchargeAmount: item.surcharge_amount,
    totalAmount: item.total_amount,
  }
}

function fromApiMonthlyClosure(closure: ApiMonthlyClosure): MonthlyClosure {
  return {
    id: closure.id,
    clinicId: closure.clinic_id,
    competenceYear: closure.competence_year,
    competenceMonth: closure.competence_month,
    periodStart: closure.period_start,
    periodEnd: closure.period_end,
    status: closure.status,
    itemCount: closure.item_count,
    subtotal: closure.subtotal,
    discountTotal: closure.discount_total,
    surchargeTotal: closure.surcharge_total,
    onCallFeeTotal: closure.on_call_fee_total,
    grandTotal: closure.grand_total,
    generatedBy: closure.generated_by,
    closedBy: closure.closed_by,
    generatedAt: closure.generated_at,
    closedAt: closure.closed_at,
    reopenedAt: closure.reopened_at,
    version: closure.version,
    items: closure.items.map(fromApiMonthlyClosureItem),
    adjustments: (closure.adjustments ?? []).map(fromApiFinancialAdjustment),
  }
}

function fromApiFinancialAdjustment(adjustment: ApiFinancialAdjustment): FinancialAdjustment {
  return {
    id: adjustment.id,
    monthlyClosureId: adjustment.monthly_closure_id,
    monthlyClosureItemId: adjustment.monthly_closure_item_id,
    kind: adjustment.kind,
    amount: adjustment.amount,
    reason: adjustment.reason,
    createdBy: adjustment.created_by,
    createdAt: adjustment.created_at,
  }
}

function fromApiMonthlyClosureSummary(closure: ApiMonthlyClosureSummary): MonthlyClosureSummary {
  return {
    id: closure.id,
    clinicId: closure.clinic_id,
    competenceYear: closure.competence_year,
    competenceMonth: closure.competence_month,
    periodStart: closure.period_start,
    periodEnd: closure.period_end,
    status: closure.status,
    itemCount: closure.item_count,
    grandTotal: closure.grand_total,
    closedBy: closure.closed_by,
    closedAt: closure.closed_at,
    version: closure.version,
  }
}

export interface CloseMonthlyPeriodParams {
  clinicId: string
  year: number
  month: number
}

export async function closeMonthlyPeriod(
  params: CloseMonthlyPeriodParams,
  idempotencyKey: string,
): Promise<MonthlyClosure> {
  const response = await fetch(`${API_BASE}/closures`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
    credentials: 'include',
    body: JSON.stringify({ clinic_id: params.clinicId, year: params.year, month: params.month }),
  })
  await throwIfNotOk(response)
  return fromApiMonthlyClosure((await response.json()) as ApiMonthlyClosure)
}

export interface MonthlyClosureListParams {
  clinicId?: string
  page?: number
  pageSize?: number
}

export async function fetchMonthlyClosures(
  params: MonthlyClosureListParams = {},
): Promise<MonthlyClosurePage> {
  const query = new URLSearchParams()
  if (params.clinicId) query.set('clinic_id', params.clinicId)
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 20))

  const response = await fetch(`${API_BASE}/closures?${query.toString()}`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiMonthlyClosurePage
  return {
    items: body.items.map(fromApiMonthlyClosureSummary),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export async function fetchMonthlyClosure(id: string): Promise<MonthlyClosure> {
  const response = await fetch(`${API_BASE}/closures/${id}`, { credentials: 'include' })
  await throwIfNotOk(response)
  return fromApiMonthlyClosure((await response.json()) as ApiMonthlyClosure)
}

export async function reopenMonthlyClosure(id: string, reason: string): Promise<MonthlyClosure> {
  const response = await fetch(`${API_BASE}/closures/${id}/reopen`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ reason }),
  })
  await throwIfNotOk(response)
  return fromApiMonthlyClosure((await response.json()) as ApiMonthlyClosure)
}

export interface AddFinancialAdjustmentParams {
  monthlyClosureItemId: string | null
  kind: FinancialAdjustmentKind
  amount: string
  reason: string
}

export async function addFinancialAdjustment(
  closureId: string,
  params: AddFinancialAdjustmentParams,
): Promise<FinancialAdjustment> {
  const response = await fetch(`${API_BASE}/closures/${closureId}/adjustments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      monthly_closure_item_id: params.monthlyClosureItemId,
      kind: params.kind,
      amount: params.amount,
      reason: params.reason,
    }),
  })
  await throwIfNotOk(response)
  return fromApiFinancialAdjustment((await response.json()) as ApiFinancialAdjustment)
}

export function monthlyClosureExportUrl(id: string): string {
  return `${API_BASE}/closures/${id}/export`
}
