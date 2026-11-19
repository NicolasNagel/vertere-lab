import { apiRequest } from '../../../shared/api/http-client'

export type PatientSex = 'MALE' | 'FEMALE'
export type PatientStatus = 'ACTIVE' | 'INACTIVE'
export type PatientAgeUnit = 'YEARS' | 'MONTHS'

export const AGE_UNIT_LABELS: Record<PatientAgeUnit, string> = {
  YEARS: 'anos',
  MONTHS: 'meses',
}

export interface Patient {
  id: string
  clinicId: string | null
  name: string
  speciesId: string
  sex: PatientSex
  breed: string | null
  ageDescription: string | null
  ageValue: number | null
  ageUnit: PatientAgeUnit | null
  ageRecordedOn: string | null
  ownerName: string
  ownerPhone: string | null
  ownerDocument: string | null
  status: PatientStatus
  notes: string | null
  createdAt: string
  updatedAt: string
  rowVersion: number
}

export interface PatientPage {
  items: Patient[]
  total: number
  page: number
  pageSize: number
}

export interface PatientListParams {
  clinicId?: string
  speciesId?: string
  search?: string
  status?: PatientStatus
  page?: number
  pageSize?: number
}

export interface PatientFormValues {
  clinicId: string
  name: string
  speciesId: string
  sex: PatientSex
  breed: string | null
  ageValue: number | null
  ageUnit: PatientAgeUnit | null
  ownerName: string
  ownerPhone: string | null
  ownerDocument: string | null
  notes: string | null
}

export interface Species {
  id: string
  name: string
}

interface ApiPatient {
  id: string
  clinic_id: string | null
  name: string
  species_id: string
  sex: PatientSex
  breed: string | null
  age_description: string | null
  age_value: number | null
  age_unit: PatientAgeUnit | null
  age_recorded_on: string | null
  owner_name: string
  owner_phone: string | null
  owner_document: string | null
  status: PatientStatus
  notes: string | null
  created_at: string
  updated_at: string
  row_version: number
}

interface ApiPatientPage {
  items: ApiPatient[]
  total: number
  page: number
  page_size: number
}

interface ApiSpecies {
  id: string
  name: string
  created_at: string
}

function fromApiPatient(patient: ApiPatient): Patient {
  return {
    id: patient.id,
    clinicId: patient.clinic_id,
    name: patient.name,
    speciesId: patient.species_id,
    sex: patient.sex,
    breed: patient.breed,
    ageDescription: patient.age_description,
    ageValue: patient.age_value,
    ageUnit: patient.age_unit,
    ageRecordedOn: patient.age_recorded_on,
    ownerName: patient.owner_name,
    ownerPhone: patient.owner_phone,
    ownerDocument: patient.owner_document,
    status: patient.status,
    notes: patient.notes,
    createdAt: patient.created_at,
    updatedAt: patient.updated_at,
    rowVersion: patient.row_version,
  }
}

function toApiPayload(values: PatientFormValues): Record<string, unknown> {
  return {
    clinic_id: values.clinicId,
    name: values.name,
    species_id: values.speciesId,
    sex: values.sex,
    breed: values.breed || null,
    age_value: values.ageValue,
    age_unit: values.ageValue === null ? null : values.ageUnit,
    owner_name: values.ownerName,
    owner_phone: values.ownerPhone || null,
    owner_document: values.ownerDocument || null,
    notes: values.notes || null,
  }
}

export async function fetchPatients(params: PatientListParams = {}): Promise<PatientPage> {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.clinicId) query.set('clinic_id', params.clinicId)
  if (params.speciesId) query.set('species_id', params.speciesId)
  if (params.status) query.set('status', params.status)
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 20))

  const body = await apiRequest<ApiPatientPage>(`/patients?${query.toString()}`)
  return {
    items: body.items.map(fromApiPatient),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export interface PatientsSummaryParams {
  search?: string
  clinicId?: string
  speciesId?: string
}

export interface PatientsSummary {
  total: number
  active: number
  inactive: number
}

/** Contagens por status do servidor, com o mesmo escopo e filtros da lista (menos o status). */
export async function fetchPatientsSummary(
  params: PatientsSummaryParams = {},
): Promise<PatientsSummary> {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.clinicId) query.set('clinic_id', params.clinicId)
  if (params.speciesId) query.set('species_id', params.speciesId)

  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return apiRequest<PatientsSummary>(`/patients/summary${suffix}`)
}

export async function fetchPatient(id: string): Promise<Patient> {
  return fromApiPatient(await apiRequest<ApiPatient>(`/patients/${id}`))
}

export async function createPatient(values: PatientFormValues): Promise<Patient> {
  const patient = await apiRequest<ApiPatient>('/patients', {
    method: 'POST',
    body: toApiPayload(values),
  })
  return fromApiPatient(patient)
}

export async function updatePatient(
  id: string,
  values: PatientFormValues & { status: PatientStatus; expectedRowVersion: number },
): Promise<Patient> {
  const patient = await apiRequest<ApiPatient>(`/patients/${id}`, {
    method: 'PATCH',
    body: {
      ...toApiPayload(values),
      status: values.status,
      expected_row_version: values.expectedRowVersion,
    },
  })
  return fromApiPatient(patient)
}

export async function deactivatePatient(id: string): Promise<Patient> {
  const patient = await apiRequest<ApiPatient>(`/patients/${id}/deactivate`, {
    method: 'POST',
  })
  return fromApiPatient(patient)
}

export async function reactivatePatient(id: string): Promise<Patient> {
  const patient = await apiRequest<ApiPatient>(`/patients/${id}/reactivate`, {
    method: 'POST',
  })
  return fromApiPatient(patient)
}

export async function fetchSpecies(): Promise<Species[]> {
  const body = await apiRequest<{ items: ApiSpecies[] }>('/species')
  return body.items.map((item) => ({ id: item.id, name: item.name }))
}
