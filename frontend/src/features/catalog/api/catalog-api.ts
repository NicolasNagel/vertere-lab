import { apiRequest } from '../../../shared/api/http-client'

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
  /** Pacote/perfil: exames que o compõem (vazio para exame avulso). */
  componentExamIds: string[]
  isPanel: boolean
  status: ExamStatus
  rowVersion: number
  priceBase: string | null
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
  name: string
  categoryId: string
  priceBase: string | null
  description: string | null
  speciesIds: string[]
  componentExamIds?: string[]
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
  component_exam_ids: string[]
  is_panel: boolean
  status: ExamStatus
  row_version: number
  price_base: string | null
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
    componentExamIds: exam.component_exam_ids,
    isPanel: exam.is_panel,
    status: exam.status,
    rowVersion: exam.row_version,
    priceBase: exam.price_base,
    updatedAt: exam.updated_at,
  }
}

function toApiExamPayload(values: ExamFormValues): Record<string, unknown> {
  return {
    name: values.name,
    category_id: values.categoryId,
    // null = manter o preço atual (quem não gere preço não o envia).
    price_base: values.priceBase ?? undefined,
    description: values.description || null,
    species_ids: values.speciesIds,
    component_exam_ids: values.componentExamIds ?? [],
  }
}

export async function fetchActiveExamCategories(): Promise<ExamCategory[]> {
  const body = await apiRequest<ApiExamCategoryListResponse>('/exam-categories/active')
  return body.items.map(fromApiCategory)
}

export async function createExamCategory(name: string): Promise<ExamCategory> {
  const category = await apiRequest<ApiExamCategory>('/exam-categories', {
    method: 'POST',
    body: { name },
  })
  return fromApiCategory(category)
}

// Fetches a single category regardless of status — used to resolve the
// label of an exam's category when it has since been deactivated and so
// no longer appears in fetchActiveExamCategories().
export async function fetchExamCategory(id: string): Promise<ExamCategory> {
  return fromApiCategory(await apiRequest<ApiExamCategory>(`/exam-categories/${id}`))
}

export async function fetchExams(params: ExamListParams = {}): Promise<ExamPage> {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.status) query.set('status', params.status)
  if (params.categoryId) query.set('category_id', params.categoryId)
  if (params.speciesId) query.set('species_id', params.speciesId)
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 20))

  const body = await apiRequest<ApiExamPage>(`/exams?${query.toString()}`)
  return {
    items: body.items.map(fromApiExam),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export async function fetchExam(id: string): Promise<Exam> {
  return fromApiExam(await apiRequest<ApiExam>(`/exams/${id}`))
}

export async function createExam(values: ExamFormValues): Promise<Exam> {
  const exam = await apiRequest<ApiExam>('/exams', {
    method: 'POST',
    body: toApiExamPayload(values),
  })
  return fromApiExam(exam)
}

export async function updateExam(
  id: string,
  values: ExamFormValues & {
    status: ExamStatus
    expectedRowVersion: number
    reason?: string | null
  },
): Promise<Exam> {
  const exam = await apiRequest<ApiExam>(`/exams/${id}`, {
    method: 'PATCH',
    body: {
      ...toApiExamPayload(values),
      status: values.status,
      expected_row_version: values.expectedRowVersion,
      reason: values.reason || undefined,
    },
  })
  return fromApiExam(exam)
}

export async function deactivateExam(id: string): Promise<Exam> {
  const exam = await apiRequest<ApiExam>(`/exams/${id}/deactivate`, {
    method: 'POST',
  })
  return fromApiExam(exam)
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
  const body = await apiRequest<ApiExamImportResponse>('/exams/import', {
    method: 'POST',
    body: formData,
  })
  return {
    importedCount: body.imported_count,
    errors: body.errors.map((error) => ({ line: error.line, message: error.message })),
  }
}
