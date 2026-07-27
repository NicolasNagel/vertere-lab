import { throwIfNotOk } from '../../../shared/api/errors'

const API_BASE = '/api/v1'

export type ExamCategoryStatus = 'ACTIVE' | 'INACTIVE'
export type ExamStatus = 'ACTIVE' | 'INACTIVE'

export interface ExamCategory {
  id: string
  name: string
  status: ExamCategoryStatus
  rowVersion: number
}

// null when the API omitted the field because the actor lacks
// `pricing.read` — never a client-side hide (mirrors
// backend/app/modules/catalog/api/schemas.py::ExamRead).
export interface Exam {
  id: string
  code: string
  name: string
  categoryId: string
  description: string | null
  speciesIds: string[]
  status: ExamStatus
  rowVersion: number
  priceBase: string | null
  plantaoSurchargeFixed: string | null
  plantaoSurchargePercent: string | null
  updatedAt: string
}

export interface ExamPage {
  items: Exam[]
  total: number
  page: number
  pageSize: number
}

export interface ExamListParams {
  search?: string
  status?: ExamStatus
  categoryId?: string
  speciesId?: string
  page?: number
  pageSize?: number
}

export interface ExamFormValues {
  code: string
  name: string
  categoryId: string
  priceBase: string
  description: string | null
  plantaoSurchargeFixed: string | null
  plantaoSurchargePercent: string | null
  speciesIds: string[]
}

interface ApiExamCategory {
  id: string
  name: string
  status: ExamCategoryStatus
  row_version: number
}

interface ApiExamCategoryListResponse {
  items: ApiExamCategory[]
}

interface ApiExam {
  id: string
  code: string
  name: string
  category_id: string
  description: string | null
  species_ids: string[]
  status: ExamStatus
  row_version: number
  price_base: string | null
  plantao_surcharge_fixed: string | null
  plantao_surcharge_percent: string | null
  updated_at: string
}

interface ApiExamPage {
  items: ApiExam[]
  total: number
  page: number
  page_size: number
}

function fromApiCategory(category: ApiExamCategory): ExamCategory {
  return {
    id: category.id,
    name: category.name,
    status: category.status,
    rowVersion: category.row_version,
  }
}

function fromApiExam(exam: ApiExam): Exam {
  return {
    id: exam.id,
    code: exam.code,
    name: exam.name,
    categoryId: exam.category_id,
    description: exam.description,
    speciesIds: exam.species_ids,
    status: exam.status,
    rowVersion: exam.row_version,
    priceBase: exam.price_base,
    plantaoSurchargeFixed: exam.plantao_surcharge_fixed,
    plantaoSurchargePercent: exam.plantao_surcharge_percent,
    updatedAt: exam.updated_at,
  }
}

function toApiExamPayload(values: ExamFormValues): Record<string, unknown> {
  return {
    code: values.code,
    name: values.name,
    category_id: values.categoryId,
    price_base: values.priceBase,
    description: values.description || null,
    plantao_surcharge_fixed: values.plantaoSurchargeFixed || null,
    plantao_surcharge_percent: values.plantaoSurchargePercent || null,
    species_ids: values.speciesIds,
  }
}

export async function fetchActiveExamCategories(): Promise<ExamCategory[]> {
  const response = await fetch(`${API_BASE}/exam-categories/active`, { credentials: 'include' })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiExamCategoryListResponse
  return body.items.map(fromApiCategory)
}

export async function createExamCategory(name: string): Promise<ExamCategory> {
  const response = await fetch(`${API_BASE}/exam-categories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name }),
  })
  await throwIfNotOk(response)
  return fromApiCategory((await response.json()) as ApiExamCategory)
}

// Fetches a single category regardless of status — used to resolve the
// label of an exam's category when it has since been deactivated and so
// no longer appears in fetchActiveExamCategories().
export async function fetchExamCategory(id: string): Promise<ExamCategory> {
  const response = await fetch(`${API_BASE}/exam-categories/${id}`, { credentials: 'include' })
  await throwIfNotOk(response)
  return fromApiCategory((await response.json()) as ApiExamCategory)
}

export async function fetchExams(params: ExamListParams = {}): Promise<ExamPage> {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.status) query.set('status', params.status)
  if (params.categoryId) query.set('category_id', params.categoryId)
  if (params.speciesId) query.set('species_id', params.speciesId)
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 20))

  const response = await fetch(`${API_BASE}/exams?${query.toString()}`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiExamPage
  return {
    items: body.items.map(fromApiExam),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export async function fetchExam(id: string): Promise<Exam> {
  const response = await fetch(`${API_BASE}/exams/${id}`, { credentials: 'include' })
  await throwIfNotOk(response)
  return fromApiExam((await response.json()) as ApiExam)
}

export async function createExam(values: ExamFormValues): Promise<Exam> {
  const response = await fetch(`${API_BASE}/exams`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(toApiExamPayload(values)),
  })
  await throwIfNotOk(response)
  return fromApiExam((await response.json()) as ApiExam)
}

export async function updateExam(
  id: string,
  values: ExamFormValues & { status: ExamStatus; expectedRowVersion: number },
): Promise<Exam> {
  const response = await fetch(`${API_BASE}/exams/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      ...toApiExamPayload(values),
      status: values.status,
      expected_row_version: values.expectedRowVersion,
    }),
  })
  await throwIfNotOk(response)
  return fromApiExam((await response.json()) as ApiExam)
}

export async function deactivateExam(id: string): Promise<Exam> {
  const response = await fetch(`${API_BASE}/exams/${id}/deactivate`, {
    method: 'POST',
    credentials: 'include',
  })
  await throwIfNotOk(response)
  return fromApiExam((await response.json()) as ApiExam)
}

export interface ExamImportRowError {
  line: number
  message: string
}

export interface ExamImportResult {
  importedCount: number
  errors: ExamImportRowError[]
}

interface ApiExamImportResponse {
  imported_count: number
  errors: { line: number; message: string }[]
}

export async function importExams(file: File): Promise<ExamImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${API_BASE}/exams/import`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiExamImportResponse
  return {
    importedCount: body.imported_count,
    errors: body.errors.map((error) => ({ line: error.line, message: error.message })),
  }
}
