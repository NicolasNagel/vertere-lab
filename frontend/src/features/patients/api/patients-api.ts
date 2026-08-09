import { throwIfNotOk } from '../../../shared/api/errors'

const API_BASE = '/api/v1'

export type PatientSex = 'MALE' | 'FEMALE'
export type PatientStatus = 'ACTIVE' | 'INACTIVE'

export interface Patient {
  id: string
  clinicId: string | null
  name: string
  speciesId: string
  sex: PatientSex
  breed: string | null
  ageDescription: string | null
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
  ageDescription: string | null
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
    age_description: values.ageDescription || null,
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
  if (params.status) query.set('status', params.status)
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 20))

  const response = await fetch(`${API_BASE}/patients?${query.toString()}`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiPatientPage
  return {
    items: body.items.map(fromApiPatient),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export async function fetchPatient(id: string): Promise<Patient> {
  const response = await fetch(`${API_BASE}/patients/${id}`, { credentials: 'include' })
  await throwIfNotOk(response)
  return fromApiPatient((await response.json()) as ApiPatient)
}

export async function createPatient(values: PatientFormValues): Promise<Patient> {
  const response = await fetch(`${API_BASE}/patients`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(toApiPayload(values)),
  })
  await throwIfNotOk(response)
  return fromApiPatient((await response.json()) as ApiPatient)
}

export async function updatePatient(
  id: string,
  values: PatientFormValues & { status: PatientStatus; expectedRowVersion: number },
): Promise<Patient> {
  const response = await fetch(`${API_BASE}/patients/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      ...toApiPayload(values),
      status: values.status,
      expected_row_version: values.expectedRowVersion,
    }),
  })
  await throwIfNotOk(response)
  return fromApiPatient((await response.json()) as ApiPatient)
}

export async function deactivatePatient(id: string): Promise<Patient> {
  const response = await fetch(`${API_BASE}/patients/${id}/deactivate`, {
    method: 'POST',
    credentials: 'include',
  })
  await throwIfNotOk(response)
  return fromApiPatient((await response.json()) as ApiPatient)
}

export async function fetchSpecies(): Promise<Species[]> {
  const response = await fetch(`${API_BASE}/species`, { credentials: 'include' })
  await throwIfNotOk(response)
  const body = (await response.json()) as { items: ApiSpecies[] }
  return body.items.map((item) => ({ id: item.id, name: item.name }))
}
