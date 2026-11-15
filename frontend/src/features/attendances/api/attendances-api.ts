import { apiRequest } from '../../../shared/api/http-client'
import type {
  AttendanceListResponse as GeneratedAttendancePage,
  AttendancePreviewResponse as GeneratedAttendancePreview,
  AttendanceRead as GeneratedAttendance,
  AttendanceTimelineResponse as GeneratedAttendanceTimelinePage,
} from '../../../shared/api/generated'

export type AttendanceStatus =
  | 'DRAFT'
  | 'CONFIRMED'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'ON_HOLD'

/** Status em que o atendimento ainda pode ser cancelado (mesma regra da lista e do detalhe). */
export const CANCELLABLE_STATUSES: ReadonlySet<AttendanceStatus> = new Set(['DRAFT', 'CONFIRMED'])

export type CollectionMethod = 'HELITO_NICOLAS' | 'INTERNAL' | 'MARLI' | 'COURIER' | 'UBER'
export type ServiceLevel = 'NORMAL' | 'PLANTAO_NORMAL' | 'PLANTAO_ESPECIAL'

/** Rótulo de exibição único por `ServiceLevel` — evita 5 lugares reimplementando
 * o mesmo `=== 'PLANTAO_NORMAL' ? ... : ...` cada um com um pedaço diferente da
 * regra (ver `docs/adr` — taxa fixa por atendimento substituiu o antigo +30%). */
export const COLLECTION_METHOD_LABELS: Record<CollectionMethod, string> = {
  INTERNAL: 'Internos',
  HELITO_NICOLAS: 'Helito/Nicolas',
  MARLI: 'Marli',
  COURIER: 'Motoboy',
  UBER: 'Uber',
}

export const SERVICE_LEVEL_LABELS: Record<ServiceLevel, string> = {
  NORMAL: 'Normal',
  PLANTAO_NORMAL: 'Plantão Normal',
  PLANTAO_ESPECIAL: 'Plantão Especial',
}

export interface AttendanceExamItem {
  id: string
  examId: string
  examCode: string
  examName: string
  priceBase: string
  /** Composição congelada quando o item é um pacote; vazio para exame avulso. */
  components: { code: string; name: string }[]
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
  collectionMethod: CollectionMethod
  serviceLevel: ServiceLevel
  serviceDate: string | null
  notes: string | null
  status: AttendanceStatus
  items: AttendanceExamItem[]
  billingCompetence: string | null
  subtotal: string
  discountTotal: string
  surchargeTotal: string
  onCallFee: string
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
  serviceLevel?: ServiceLevel
  protocolNumber?: string
  ownerName?: string
  serviceDateFrom?: string
  serviceDateTo?: string
  page?: number
  pageSize?: number
}

export interface AttendanceStatusCounts {
  total: number
  byStatus: Partial<Record<AttendanceStatus, number>>
  /** Server-computed: DRAFT and CANCELLED excluded, whole filter (not one page). */
  billedTotal: string
}

export interface AttendanceDraftFormValues {
  clinicId: string
  veterinarianId: string
  patientId: string
  collectionMethod: CollectionMethod
  serviceLevel: ServiceLevel
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
  collectionMethod: CollectionMethod
  serviceLevel: ServiceLevel
  serviceDate: string
  items: AttendanceExamItem[]
  subtotal: string
  discountTotal: string
  surchargeTotal: string
  onCallFee: string
  grandTotal: string
}

export interface AttendanceTimelineEntry {
  id: string
  occurredAt: string
  actorUserId: string | null
  actorName: string | null
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

// Sem `pricing.read` a API devolve null nos valores; a tela nem os mostra.
const ZERO = '0.00'

interface ApiAttendanceExamItem {
  id: string
  exam_id: string
  exam_code: string
  exam_name: string
  price_base: string | null
  components: { code: string; name: string }[]
  quantity: number
  discount_amount: string | null
  surcharge_amount: string | null
  total_amount: string | null
  override_reason: string | null
  status: 'ACTIVE' | 'CANCELLED'
}

interface ApiAttendance extends GeneratedAttendance {
  id: string
  clinic_id: string
  veterinarian_id: string
  patient_id: string
  collection_method: CollectionMethod
  service_level: ServiceLevel
  service_date: string | null
  notes: string | null
  status: AttendanceStatus
  items: ApiAttendanceExamItem[]
  billing_competence: string | null
  subtotal: string | null
  discount_total: string | null
  surcharge_total: string | null
  on_call_fee: string | null
  grand_total: string | null
  protocol_number: string | null
  cancel_reason: string | null
  created_at: string
  updated_at: string
  row_version: number
}

interface ApiAttendancePage extends GeneratedAttendancePage {
  items: ApiAttendance[]
  total: number
  page: number
  page_size: number
}

interface ApiAttendancePreview extends GeneratedAttendancePreview {
  attendance_id: string
  clinic_id: string
  veterinarian_id: string
  patient_id: string
  collection_method: CollectionMethod
  service_level: ServiceLevel
  service_date: string
  items: ApiAttendanceExamItem[]
  subtotal: string | null
  discount_total: string | null
  surcharge_total: string | null
  on_call_fee: string | null
  grand_total: string | null
}

interface ApiAttendanceTimelineEntry {
  id: string
  occurred_at: string
  actor_user_id: string | null
  actor_name?: string | null
  action: string
  before_state: Record<string, unknown> | null
  after_state: Record<string, unknown> | null
  reason: string | null
}

interface ApiAttendanceTimelinePage extends GeneratedAttendanceTimelinePage {
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
    collectionMethod: preview.collection_method ?? 'INTERNAL',
    serviceLevel: preview.service_level ?? 'NORMAL',
    serviceDate: preview.service_date,
    items: preview.items.map(fromApiItem),
    subtotal: preview.subtotal ?? ZERO,
    discountTotal: preview.discount_total ?? ZERO,
    surchargeTotal: preview.surcharge_total ?? ZERO,
    onCallFee: preview.on_call_fee ?? ZERO,
    grandTotal: preview.grand_total ?? ZERO,
  }
}

function fromApiItem(item: ApiAttendanceExamItem): AttendanceExamItem {
  return {
    id: item.id,
    examId: item.exam_id,
    examCode: item.exam_code,
    examName: item.exam_name,
    priceBase: item.price_base ?? ZERO,
    components: item.components,
    quantity: item.quantity,
    discountAmount: item.discount_amount ?? ZERO,
    surchargeAmount: item.surcharge_amount ?? ZERO,
    totalAmount: item.total_amount ?? ZERO,
    overrideReason: item.override_reason,
    status: item.status,
  }
}

function fromApiTimelineEntry(entry: ApiAttendanceTimelineEntry): AttendanceTimelineEntry {
  return {
    id: entry.id,
    occurredAt: entry.occurred_at,
    actorUserId: entry.actor_user_id,
    actorName: entry.actor_name ?? null,
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
    collectionMethod: attendance.collection_method ?? 'INTERNAL',
    serviceLevel: attendance.service_level ?? 'NORMAL',
    serviceDate: attendance.service_date,
    notes: attendance.notes,
    status: attendance.status,
    items: attendance.items.map(fromApiItem),
    billingCompetence: attendance.billing_competence,
    subtotal: attendance.subtotal ?? ZERO,
    discountTotal: attendance.discount_total ?? ZERO,
    surchargeTotal: attendance.surcharge_total ?? ZERO,
    onCallFee: attendance.on_call_fee ?? ZERO,
    grandTotal: attendance.grand_total ?? ZERO,
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
  if (params.serviceLevel) query.set('service_level', params.serviceLevel)
  if (params.protocolNumber) query.set('protocol_number', params.protocolNumber)
  if (params.ownerName) query.set('owner_name', params.ownerName)
  if (params.serviceDateFrom) query.set('service_date_from', params.serviceDateFrom)
  if (params.serviceDateTo) query.set('service_date_to', params.serviceDateTo)
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 20))

  const body = await apiRequest<ApiAttendancePage>(`/attendances?${query.toString()}`)
  return {
    items: body.items.map(fromApiAttendance),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export type AttendanceStatusCountsParams = Omit<AttendanceListParams, 'page' | 'pageSize' | 'status'>

export async function fetchAttendanceStatusCounts(
  params: AttendanceStatusCountsParams = {},
): Promise<AttendanceStatusCounts> {
  const query = new URLSearchParams()
  if (params.clinicId) query.set('clinic_id', params.clinicId)
  if (params.veterinarianId) query.set('veterinarian_id', params.veterinarianId)
  if (params.serviceLevel) query.set('service_level', params.serviceLevel)
  if (params.protocolNumber) query.set('protocol_number', params.protocolNumber)
  if (params.ownerName) query.set('owner_name', params.ownerName)
  if (params.serviceDateFrom) query.set('service_date_from', params.serviceDateFrom)
  if (params.serviceDateTo) query.set('service_date_to', params.serviceDateTo)

  const body = await apiRequest<{
    total: number
    by_status: Record<string, number>
    billed_total: string | null
  }>(
    `/attendances/status-counts?${query.toString()}`,
  )
  return {
    total: body.total,
    byStatus: body.by_status as Partial<Record<AttendanceStatus, number>>,
    billedTotal: body.billed_total ?? ZERO,
  }
}

export async function fetchAttendance(id: string): Promise<Attendance> {
  return fromApiAttendance(await apiRequest<ApiAttendance>(`/attendances/${id}`))
}

export async function previewAttendance(
  id: string,
  items: AttendanceConfirmItemInput[],
): Promise<AttendancePreview> {
  const body = await apiRequest<ApiAttendancePreview>(`/attendances/${id}/preview`, {
    method: 'POST',
    body: { items: toApiConfirmItems(items) },
  })
  return fromApiPreview(body)
}

export async function confirmAttendance(
  id: string,
  items: AttendanceConfirmItemInput[],
  idempotencyKey: string,
): Promise<Attendance> {
  const body = await apiRequest<ApiAttendance>(`/attendances/${id}/confirm`, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: { items: toApiConfirmItems(items) },
  })
  return fromApiAttendance(body)
}

export async function cancelAttendance(id: string, reason: string): Promise<Attendance> {
  const body = await apiRequest<ApiAttendance>(`/attendances/${id}/cancel`, {
    method: 'POST',
    body: { reason },
  })
  return fromApiAttendance(body)
}

export interface AttendanceUpdateInput {
  clinicId?: string
  veterinarianId?: string
  patientId?: string
  collectionMethod?: CollectionMethod
  serviceLevel?: ServiceLevel
  serviceDate?: string | null
  notes?: string
  /** Obrigatório fora do rascunho; vai para a auditoria. */
  reason?: string
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
  if (input.collectionMethod !== undefined) body.collection_method = input.collectionMethod
  if (input.serviceLevel !== undefined) body.service_level = input.serviceLevel
  if (input.serviceDate !== undefined) body.service_date = input.serviceDate
  if (input.notes !== undefined) body.notes = input.notes
  if (input.reason !== undefined) body.reason = input.reason

  const responseBody = await apiRequest<ApiAttendance>(`/attendances/${id}`, {
    method: 'PATCH',
    body,
  })
  return fromApiAttendance(responseBody)
}

/** One line of the desired exam set: `itemId` keeps an existing line (price snapshot stays),
 * `examId` adds a new one priced on the attendance's service date. Lines left out are removed
 * (the backend keeps them in history as cancelled). */
export interface AttendanceItemEditInput {
  itemId?: string
  examId?: string
  quantity: number
  discountAmount?: string | null
  overrideReason?: string | null
}

export async function updateAttendanceItems(
  id: string,
  rowVersion: number,
  reason: string,
  items: AttendanceItemEditInput[],
): Promise<Attendance> {
  const responseBody = await apiRequest<ApiAttendance>(`/attendances/${id}/items`, {
    method: 'PUT',
    body: {
      row_version: rowVersion,
      reason,
      items: items.map((item) => ({
        item_id: item.itemId,
        exam_id: item.examId,
        quantity: item.quantity,
        discount_amount: item.discountAmount || undefined,
        override_reason: item.overrideReason || undefined,
      })),
    },
  })
  return fromApiAttendance(responseBody)
}

export async function fetchAttendanceTimeline(
  id: string,
  page: number,
  pageSize: number,
): Promise<AttendanceTimelinePage> {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  const body = await apiRequest<ApiAttendanceTimelinePage>(
    `/attendances/${id}/timeline?${query.toString()}`,
  )
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
  const body = await apiRequest<ApiAttendance>('/attendances/drafts', {
    method: 'POST',
    body: {
      clinic_id: values.clinicId,
      veterinarian_id: values.veterinarianId,
      patient_id: values.patientId,
      collection_method: values.collectionMethod,
      service_level: values.serviceLevel,
      service_date: values.serviceDate,
      notes: values.notes,
    },
  })
  return fromApiAttendance(body)
}
