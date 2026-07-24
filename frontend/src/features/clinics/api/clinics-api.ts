import { throwIfNotOk } from '../../../shared/api/errors'

const API_BASE = '/api/v1'

export type ClinicStatus = 'ACTIVE' | 'INACTIVE' | 'DELINQUENT' | 'SPECIAL'

export interface Clinic {
  id: string
  name: string
  taxId: string | null
  phone: string | null
  email: string | null
  status: ClinicStatus
  addressZipCode: string | null
  addressStreet: string | null
  addressNumber: string | null
  addressNeighborhood: string | null
  addressCity: string | null
  addressState: string | null
  addressComplement: string | null
  notes: string | null
  createdAt: string
  updatedAt: string
  rowVersion: number
}

export interface ClinicPage {
  items: Clinic[]
  total: number
  page: number
  pageSize: number
}

export interface ClinicListParams {
  search?: string
  status?: ClinicStatus
  page?: number
  pageSize?: number
}

export interface ClinicFormValues {
  name: string
  taxId: string | null
  phone: string | null
  email: string | null
  addressZipCode: string | null
  addressStreet: string | null
  addressNumber: string | null
  addressNeighborhood: string | null
  addressCity: string | null
  addressState: string | null
  addressComplement: string | null
  notes: string | null
}

interface ApiClinic {
  id: string
  name: string
  tax_id: string | null
  phone: string | null
  email: string | null
  status: ClinicStatus
  address_zip_code: string | null
  address_street: string | null
  address_number: string | null
  address_neighborhood: string | null
  address_city: string | null
  address_state: string | null
  address_complement: string | null
  notes: string | null
  created_at: string
  updated_at: string
  row_version: number
}

interface ApiClinicPage {
  items: ApiClinic[]
  total: number
  page: number
  page_size: number
}

function fromApiClinic(clinic: ApiClinic): Clinic {
  return {
    id: clinic.id,
    name: clinic.name,
    taxId: clinic.tax_id,
    phone: clinic.phone,
    email: clinic.email,
    status: clinic.status,
    addressZipCode: clinic.address_zip_code,
    addressStreet: clinic.address_street,
    addressNumber: clinic.address_number,
    addressNeighborhood: clinic.address_neighborhood,
    addressCity: clinic.address_city,
    addressState: clinic.address_state,
    addressComplement: clinic.address_complement,
    notes: clinic.notes,
    createdAt: clinic.created_at,
    updatedAt: clinic.updated_at,
    rowVersion: clinic.row_version,
  }
}

function toApiPayload(values: ClinicFormValues): Record<string, unknown> {
  return {
    name: values.name,
    tax_id: values.taxId || null,
    phone: values.phone || null,
    email: values.email || null,
    address_zip_code: values.addressZipCode || null,
    address_street: values.addressStreet || null,
    address_number: values.addressNumber || null,
    address_neighborhood: values.addressNeighborhood || null,
    address_city: values.addressCity || null,
    address_state: values.addressState || null,
    address_complement: values.addressComplement || null,
    notes: values.notes || null,
  }
}

export async function fetchClinics(params: ClinicListParams = {}): Promise<ClinicPage> {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.status) query.set('status', params.status)
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 20))

  const response = await fetch(`${API_BASE}/clinics?${query.toString()}`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiClinicPage
  return {
    items: body.items.map(fromApiClinic),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export async function fetchClinic(id: string): Promise<Clinic> {
  const response = await fetch(`${API_BASE}/clinics/${id}`, { credentials: 'include' })
  await throwIfNotOk(response)
  return fromApiClinic((await response.json()) as ApiClinic)
}

export async function createClinic(values: ClinicFormValues): Promise<Clinic> {
  const response = await fetch(`${API_BASE}/clinics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(toApiPayload(values)),
  })
  await throwIfNotOk(response)
  return fromApiClinic((await response.json()) as ApiClinic)
}

export async function updateClinic(
  id: string,
  values: ClinicFormValues & { status: ClinicStatus; expectedRowVersion: number },
): Promise<Clinic> {
  const response = await fetch(`${API_BASE}/clinics/${id}`, {
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
  return fromApiClinic((await response.json()) as ApiClinic)
}

export async function deactivateClinic(id: string): Promise<Clinic> {
  const response = await fetch(`${API_BASE}/clinics/${id}/deactivate`, {
    method: 'POST',
    credentials: 'include',
  })
  await throwIfNotOk(response)
  return fromApiClinic((await response.json()) as ApiClinic)
}
