import { apiRequest } from '../../../shared/api/http-client'

export type VeterinarianStatus = 'ACTIVE' | 'INACTIVE'

export interface VeterinarianLinkedClinic {
  clinicId: string
  clinicName: string
  primaryClinic: boolean
}

export interface Veterinarian {
  id: string
  name: string
  crmv: string
  phone: string | null
  email: string | null
  isAutonomous: boolean
  status: VeterinarianStatus
  notes: string | null
  createdAt: string
  updatedAt: string
  rowVersion: number
  clinics: VeterinarianLinkedClinic[]
}

export interface VeterinarianPage {
  items: Veterinarian[]
  total: number
  page: number
  pageSize: number
}

export interface VeterinarianListParams {
  search?: string
  status?: VeterinarianStatus
  isAutonomous?: boolean
  /** Autônomo OU vinculado a esta clínica — mesma regra que `/confirm`
   * revalida no backend. Resolvido no servidor porque a listagem nunca
   * carrega `clinics` por item (só o endpoint de detalhe carrega). */
  availableForClinicId?: string
  page?: number
  pageSize?: number
}

export interface VeterinarianFormValues {
  name: string
  crmv: string
  phone: string | null
  email: string | null
  isAutonomous: boolean
  notes: string | null
}

interface ApiVeterinarianLinkedClinic {
  clinic_id: string
  clinic_name: string
  primary_clinic: boolean
}

interface ApiVeterinarian {
  id: string
  name: string
  crmv: string
  phone: string | null
  email: string | null
  is_autonomous: boolean
  status: VeterinarianStatus
  notes: string | null
  created_at: string
  updated_at: string
  row_version: number
  clinics?: ApiVeterinarianLinkedClinic[]
}

interface ApiVeterinarianPage {
  items: ApiVeterinarian[]
  total: number
  page: number
  page_size: number
}

function fromApiVeterinarian(veterinarian: ApiVeterinarian): Veterinarian {
  return {
    id: veterinarian.id,
    name: veterinarian.name,
    crmv: veterinarian.crmv,
    phone: veterinarian.phone,
    email: veterinarian.email,
    isAutonomous: veterinarian.is_autonomous,
    status: veterinarian.status,
    notes: veterinarian.notes,
    createdAt: veterinarian.created_at,
    updatedAt: veterinarian.updated_at,
    rowVersion: veterinarian.row_version,
    clinics: (veterinarian.clinics ?? []).map((clinic) => ({
      clinicId: clinic.clinic_id,
      clinicName: clinic.clinic_name,
      primaryClinic: clinic.primary_clinic,
    })),
  }
}

function toApiPayload(values: VeterinarianFormValues): Record<string, unknown> {
  return {
    name: values.name,
    crmv: values.crmv,
    phone: values.phone || null,
    email: values.email || null,
    is_autonomous: values.isAutonomous,
    notes: values.notes || null,
  }
}

export async function fetchVeterinarians(
  params: VeterinarianListParams = {},
): Promise<VeterinarianPage> {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.status) query.set('status', params.status)
  if (params.isAutonomous !== undefined) query.set('is_autonomous', String(params.isAutonomous))
  if (params.availableForClinicId) {
    query.set('available_for_clinic_id', params.availableForClinicId)
  }
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 20))

  const body = await apiRequest<ApiVeterinarianPage>(`/veterinarians?${query.toString()}`)
  return {
    items: body.items.map(fromApiVeterinarian),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export async function fetchVeterinarian(id: string): Promise<Veterinarian> {
  return fromApiVeterinarian(await apiRequest<ApiVeterinarian>(`/veterinarians/${id}`))
}

export async function createVeterinarian(
  values: VeterinarianFormValues,
  clinicIds: string[] = [],
): Promise<Veterinarian> {
  // The backend now requires clinic_ids in the same request for a
  // non-autonomous veterinarian (it validates "needs >=1 clinic" at
  // creation, not only on unlink) — the first clinic in the list is the
  // primary one, same convention as before when this was a separate
  // POST .../clinics call per clinic.
  const veterinarian = await apiRequest<ApiVeterinarian>('/veterinarians', {
    method: 'POST',
    body: {
      ...toApiPayload(values),
      clinic_ids: clinicIds,
      primary_clinic_id: clinicIds[0] ?? null,
    },
  })
  return fromApiVeterinarian(veterinarian)
}

export async function updateVeterinarian(
  id: string,
  values: VeterinarianFormValues & {
    status: VeterinarianStatus
    expectedRowVersion: number
    reason: string
  },
): Promise<Veterinarian> {
  const veterinarian = await apiRequest<ApiVeterinarian>(`/veterinarians/${id}`, {
    method: 'PATCH',
    body: {
      ...toApiPayload(values),
      status: values.status,
      expected_row_version: values.expectedRowVersion,
      reason: values.reason,
    },
  })
  return fromApiVeterinarian(veterinarian)
}

export async function deactivateVeterinarian(id: string): Promise<Veterinarian> {
  const veterinarian = await apiRequest<ApiVeterinarian>(`/veterinarians/${id}/deactivate`, {
    method: 'POST',
  })
  return fromApiVeterinarian(veterinarian)
}

export async function linkVeterinarianClinic(
  veterinarianId: string,
  clinicId: string,
  reason: string,
  primary = false,
): Promise<void> {
  await apiRequest<void>(`/veterinarians/${veterinarianId}/clinics`, {
    method: 'POST',
    body: { clinic_id: clinicId, primary, reason },
  })
}

export async function unlinkVeterinarianClinic(
  veterinarianId: string,
  clinicId: string,
  reason: string,
): Promise<void> {
  const query = new URLSearchParams({ reason })
  await apiRequest<void>(
    `/veterinarians/${veterinarianId}/clinics/${clinicId}?${query.toString()}`,
    {
      method: 'DELETE',
    },
  )
}
