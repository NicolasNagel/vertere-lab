import { throwIfNotOk } from '../../../shared/api/errors'

const API_BASE = '/api/v1'

export type AttendanceStatus =
  | 'DRAFT'
  | 'CONFIRMED'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'ON_HOLD'

export interface AttendanceExamItem {
  id: string
  examId: string
  examCode: string
  examName: string
  priceBase: string
  quantity: number
  discountAmount: string
  surchargeAmount: string
  totalAmount: string
  overrideReason: string | null
  status: 'ACTIVE' | 'CANCELLED'
}

export interface Attendance {
  id: string
  clinicId: string
  veterinarianId: string
  patientId: string
  serviceDate: string | null
  notes: string | null
  status: AttendanceStatus
  items: AttendanceExamItem[]
  billingCompetence: string | null
  subtotal: string
  discountTotal: string
  surchargeTotal: string
  grandTotal: string
  protocolNumber: string | null
  cancelReason: string | null
  createdAt: string
  updatedAt: string
  rowVersion: number
}

export interface AttendancePage {
  items: Attendance[]
  total: number
  page: number
  pageSize: number
}

export interface AttendanceListParams {
  clinicId?: string
  veterinarianId?: string
  patientId?: string
  status?: AttendanceStatus
  page?: number
  pageSize?: number
}

export interface AttendanceDraftFormValues {
  clinicId: string
  veterinarianId: string
  patientId: string
  serviceDate: string | null
  notes: string | null
}

export interface AttendanceConfirmItemInput {
  examId: string
  quantity: number
  discountAmount: string | null
  overrideReason: string | null
}

export interface AttendancePreview {
  attendanceId: string
  clinicId: string
  veterinarianId: string
  patientId: string
  serviceDate: string
  items: AttendanceExamItem[]
  subtotal: string
  discountTotal: string
  surchargeTotal: string
  grandTotal: string
}

export interface AttendanceTimelineEntry {
  id: string
  occurredAt: string
  actorUserId: string | null
  action: string
  beforeState: Record<string, unknown> | null
  afterState: Record<string, unknown> | null
  reason: string | null
}

export interface AttendanceTimelinePage {
  items: AttendanceTimelineEntry[]
  total: number
  page: number
  pageSize: number
}

interface ApiAttendanceExamItem {
  id: string
  exam_id: string
  exam_code: string
  exam_name: string
  price_base: string
  quantity: number
  discount_amount: string
  surcharge_amount: string
  total_amount: string
  override_reason: string | null
  status: 'ACTIVE' | 'CANCELLED'
}

interface ApiAttendance {
  id: string
  clinic_id: string
  veterinarian_id: string
  patient_id: string
  service_date: string | null
  notes: string | null
  status: AttendanceStatus
  items: ApiAttendanceExamItem[]
  billing_competence: string | null
  subtotal: string
  discount_total: string
  surcharge_total: string
  grand_total: string
  protocol_number: string | null
  cancel_reason: string | null
  created_at: string
  updated_at: string
  row_version: number
}

interface ApiAttendancePage {
  items: ApiAttendance[]
  total: number
  page: number
  page_size: number
}

interface ApiAttendancePreview {
  attendance_id: string
  clinic_id: string
  veterinarian_id: string
  patient_id: string
  service_date: string
  items: ApiAttendanceExamItem[]
  subtotal: string
  discount_total: string
  surcharge_total: string
  grand_total: string
}

interface ApiAttendanceTimelineEntry {
  id: string
  occurred_at: string
  actor_user_id: string | null
  action: string
  before_state: Record<string, unknown> | null
  after_state: Record<string, unknown> | null
  reason: string | null
}

interface ApiAttendanceTimelinePage {
  items: ApiAttendanceTimelineEntry[]
  total: number
  page: number
  page_size: number
}

function toApiConfirmItems(items: AttendanceConfirmItemInput[]): Record<string, unknown>[] {
  return items.map((item) => ({
    exam_id: item.examId,
    quantity: item.quantity,
    discount_amount: item.discountAmount,
    override_reason: item.overrideReason,
  }))
}

function fromApiPreview(preview: ApiAttendancePreview): AttendancePreview {
  return {
    attendanceId: preview.attendance_id,
    clinicId: preview.clinic_id,
    veterinarianId: preview.veterinarian_id,
    patientId: preview.patient_id,
    serviceDate: preview.service_date,
    items: preview.items.map(fromApiItem),
    subtotal: preview.subtotal,
    discountTotal: preview.discount_total,
    surchargeTotal: preview.surcharge_total,
    grandTotal: preview.grand_total,
  }
}

function fromApiItem(item: ApiAttendanceExamItem): AttendanceExamItem {
  return {
    id: item.id,
    examId: item.exam_id,
    examCode: item.exam_code,
    examName: item.exam_name,
    priceBase: item.price_base,
    quantity: item.quantity,
    discountAmount: item.discount_amount,
    surchargeAmount: item.surcharge_amount,
    totalAmount: item.total_amount,
    overrideReason: item.override_reason,
    status: item.status,
  }
}

function fromApiTimelineEntry(entry: ApiAttendanceTimelineEntry): AttendanceTimelineEntry {
  return {
    id: entry.id,
    occurredAt: entry.occurred_at,
    actorUserId: entry.actor_user_id,
    action: entry.action,
    beforeState: entry.before_state,
    afterState: entry.after_state,
    reason: entry.reason,
  }
}

function fromApiAttendance(attendance: ApiAttendance): Attendance {
  return {
    id: attendance.id,
    clinicId: attendance.clinic_id,
    veterinarianId: attendance.veterinarian_id,
    patientId: attendance.patient_id,
    serviceDate: attendance.service_date,
    notes: attendance.notes,
    status: attendance.status,
    items: attendance.items.map(fromApiItem),
    billingCompetence: attendance.billing_competence,
    subtotal: attendance.subtotal,
    discountTotal: attendance.discount_total,
    surchargeTotal: attendance.surcharge_total,
    grandTotal: attendance.grand_total,
    protocolNumber: attendance.protocol_number,
    cancelReason: attendance.cancel_reason,
    createdAt: attendance.created_at,
    updatedAt: attendance.updated_at,
    rowVersion: attendance.row_version,
  }
}

export async function fetchAttendances(params: AttendanceListParams = {}): Promise<AttendancePage> {
  const query = new URLSearchParams()
  if (params.clinicId) query.set('clinic_id', params.clinicId)
  if (params.veterinarianId) query.set('veterinarian_id', params.veterinarianId)
  if (params.patientId) query.set('patient_id', params.patientId)
  if (params.status) query.set('status', params.status)
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 20))

  const response = await fetch(`${API_BASE}/attendances?${query.toString()}`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiAttendancePage
  return {
    items: body.items.map(fromApiAttendance),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export async function fetchAttendance(id: string): Promise<Attendance> {
  const response = await fetch(`${API_BASE}/attendances/${id}`, { credentials: 'include' })
  await throwIfNotOk(response)
  return fromApiAttendance((await response.json()) as ApiAttendance)
}

export async function previewAttendance(
  id: string,
  items: AttendanceConfirmItemInput[],
): Promise<AttendancePreview> {
  const response = await fetch(`${API_BASE}/attendances/${id}/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ items: toApiConfirmItems(items) }),
  })
  await throwIfNotOk(response)
  return fromApiPreview((await response.json()) as ApiAttendancePreview)
}

export async function confirmAttendance(
  id: string,
  items: AttendanceConfirmItemInput[],
  idempotencyKey: string,
): Promise<Attendance> {
  const response = await fetch(`${API_BASE}/attendances/${id}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
    credentials: 'include',
    body: JSON.stringify({ items: toApiConfirmItems(items) }),
  })
  await throwIfNotOk(response)
  return fromApiAttendance((await response.json()) as ApiAttendance)
}

export async function cancelAttendance(id: string, reason: string): Promise<Attendance> {
  const response = await fetch(`${API_BASE}/attendances/${id}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ reason }),
  })
  await throwIfNotOk(response)
  return fromApiAttendance((await response.json()) as ApiAttendance)
}

export interface AttendanceUpdateInput {
  clinicId?: string
  veterinarianId?: string
  patientId?: string
  serviceDate?: string | null
  notes?: string
}

/** `DRAFT` accepts every field here; `CONFIRMED` accepts only `notes` — the
 * backend enforces that split (`AttendanceRecord.update_fields`,
 * `.claude/rules/12-attendance.md`: "CONFIRMED (ainda financeiramente aberto):
 * edição controlada"), this function is just the transport. */
export async function updateAttendance(
  id: string,
  rowVersion: number,
  input: AttendanceUpdateInput,
): Promise<Attendance> {
  const body: Record<string, unknown> = { row_version: rowVersion }
  if (input.clinicId !== undefined) body.clinic_id = input.clinicId
  if (input.veterinarianId !== undefined) body.veterinarian_id = input.veterinarianId
  if (input.patientId !== undefined) body.patient_id = input.patientId
  if (input.serviceDate !== undefined) body.service_date = input.serviceDate
  if (input.notes !== undefined) body.notes = input.notes

  const response = await fetch(`${API_BASE}/attendances/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  await throwIfNotOk(response)
  return fromApiAttendance((await response.json()) as ApiAttendance)
}

export async function fetchAttendanceTimeline(
  id: string,
  page: number,
  pageSize: number,
): Promise<AttendanceTimelinePage> {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  const response = await fetch(`${API_BASE}/attendances/${id}/timeline?${query.toString()}`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiAttendanceTimelinePage
  return {
    items: body.items.map(fromApiTimelineEntry),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export async function createAttendanceDraft(
  values: AttendanceDraftFormValues,
): Promise<Attendance> {
  const response = await fetch(`${API_BASE}/attendances/drafts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      clinic_id: values.clinicId,
      veterinarian_id: values.veterinarianId,
      patient_id: values.patientId,
      service_date: values.serviceDate,
      notes: values.notes,
    }),
  })
  await throwIfNotOk(response)
  return fromApiAttendance((await response.json()) as ApiAttendance)
}
