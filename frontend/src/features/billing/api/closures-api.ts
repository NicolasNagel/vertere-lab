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
