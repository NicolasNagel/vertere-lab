import { http, HttpResponse } from 'msw'

/** Handlers e fábrica de paciente compartilhados pelos testes das telas de pacientes. */
export function meHandler(permissions: string[]) {
  return http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      user: { id: 'u1', email: 'a@b.com', full_name: 'A', role_id: 'r1', role_name: 'LAB_ADMIN' },
      permissions,
    }),
  )
}

export function speciesHandler() {
  return http.get('/api/v1/species', () =>
    HttpResponse.json({
      items: [
        { id: 's1', name: 'Cão', created_at: '2026-01-01T00:00:00Z' },
        { id: 's2', name: 'Gato', created_at: '2026-01-01T00:00:00Z' },
      ],
    }),
  )
}

export function clinicsHandler() {
  return http.get('/api/v1/clinics', () =>
    HttpResponse.json({
      items: [
        { id: 'c1', name: 'Clínica Central', status: 'ACTIVE' },
        { id: 'c2', name: 'Clínica Norte', status: 'ACTIVE' },
      ],
      total: 2,
      page: 1,
      page_size: 100,
    }),
  )
}

export function apiPatient(overrides: Record<string, unknown> = {}) {
  return {
    id: 'p1',
    clinic_id: 'c1',
    name: 'Rex',
    species_id: 's1',
    sex: 'MALE',
    breed: 'SRD',
    age_description: '2 anos',
    owner_name: 'Maria Souza',
    owner_phone: '(47) 99999-0000',
    owner_document: null,
    status: 'ACTIVE',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    row_version: 1,
    ...overrides,
  }
}
