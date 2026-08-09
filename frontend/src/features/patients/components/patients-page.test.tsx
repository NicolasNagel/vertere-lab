import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { PatientsPage } from './patients-page'

const server = setupServer(clinicsHandler())

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function meHandler(permissions: string[]) {
  return http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      user: { id: 'u1', email: 'a@b.com', full_name: 'A', role_id: 'r1', role_name: 'LAB_ADMIN' },
      permissions,
    }),
  )
}

function speciesHandler() {
  return http.get('/api/v1/species', () =>
    HttpResponse.json({
      items: [
        { id: 's1', name: 'Cão', created_at: '2026-01-01T00:00:00Z' },
        { id: 's2', name: 'Gato', created_at: '2026-01-01T00:00:00Z' },
      ],
    }),
  )
}

function clinicsHandler() {
  return http.get('/api/v1/clinics', () =>
    HttpResponse.json({
      items: [{ id: 'c1', name: 'Clínica Central', status: 'ACTIVE' }],
      total: 1,
      page: 1,
      page_size: 100,
    }),
  )
}

function patientsListHandler() {
  return http.get('/api/v1/patients', () =>
    HttpResponse.json({
      items: [
        {
          id: 'p1',
          name: 'Rex',
          species_id: 's1',
          sex: 'MALE',
          breed: 'SRD',
          age_description: '2 anos',
          owner_name: 'Maria Souza',
          owner_phone: null,
          owner_document: null,
          status: 'ACTIVE',
          notes: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    }),
  )
}

function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>,
  )
}

test('lists patients returned by the API', async () => {
  server.use(meHandler(['patients.read']), speciesHandler(), patientsListHandler())
  renderWithProviders(<PatientsPage />)

  expect(await screen.findByText('Rex')).toBeInTheDocument()
  expect(screen.getByText('Maria Souza')).toBeInTheDocument()
})

test('hides the "Novo paciente" action for a user without patients.manage', async () => {
  server.use(meHandler(['patients.read']), speciesHandler(), patientsListHandler())
  renderWithProviders(<PatientsPage />)

  await screen.findByText('Rex')
  expect(screen.queryByRole('button', { name: /Novo paciente/i })).not.toBeInTheDocument()
})

test('shows the "Novo paciente" action for a user with patients.manage', async () => {
  server.use(
    meHandler(['patients.read', 'patients.manage']),
    speciesHandler(),
    clinicsHandler(),
    patientsListHandler(),
  )
  renderWithProviders(<PatientsPage />)

  expect(await screen.findByRole('button', { name: /Novo paciente/i })).toBeInTheDocument()
})

test('creates a patient with embedded owner data and returns to the detail view', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['patients.read', 'patients.manage']),
    speciesHandler(),
    clinicsHandler(),
    patientsListHandler(),
    http.post('/api/v1/patients', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      return HttpResponse.json(
        {
          id: 'p2',
          name: body.name,
          species_id: body.species_id,
          sex: body.sex,
          breed: body.breed,
          age_description: body.age_description,
          owner_name: body.owner_name,
          owner_phone: body.owner_phone,
          owner_document: body.owner_document,
          status: 'ACTIVE',
          notes: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
        },
        { status: 201 },
      )
    }),
    http.get('/api/v1/patients/p2', () =>
      HttpResponse.json({
        id: 'p2',
        name: 'Bidu',
        species_id: 's2',
        sex: 'MALE',
        breed: null,
        age_description: null,
        owner_name: 'Joana Lima',
        owner_phone: null,
        owner_document: null,
        status: 'ACTIVE',
        notes: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        row_version: 1,
      }),
    ),
  )
  renderWithProviders(<PatientsPage />)

  await user.click(await screen.findByRole('button', { name: /Novo paciente/i }))
  await user.type(screen.getByLabelText('Nome do paciente'), 'Bidu')
  await user.selectOptions(screen.getByLabelText('Clínica'), 'Clínica Central')
  await user.selectOptions(await screen.findByLabelText('Espécie'), 'Gato')
  await user.type(screen.getByLabelText('Nome do tutor'), 'Joana Lima')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: 'Novo paciente' })).not.toBeInTheDocument(),
  )
  expect(await screen.findByRole('heading', { name: 'Bidu' })).toBeInTheDocument()
  expect(screen.getByText('Joana Lima')).toBeInTheDocument()
})

test('searches patients by owner name', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['patients.read']),
    speciesHandler(),
    http.get('/api/v1/patients', ({ request }) => {
      const url = new URL(request.url)
      const search = url.searchParams.get('search')
      if (search === 'joana') {
        return HttpResponse.json({
          items: [
            {
              id: 'p2',
              name: 'Bidu',
              species_id: 's2',
              sex: 'MALE',
              breed: null,
              age_description: null,
              owner_name: 'Joana Lima',
              owner_phone: null,
              owner_document: null,
              status: 'ACTIVE',
              notes: null,
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              row_version: 1,
            },
          ],
          total: 1,
          page: 1,
          page_size: 100,
        })
      }
      return HttpResponse.json({
        items: [
          {
            id: 'p1',
            name: 'Rex',
            species_id: 's1',
            sex: 'MALE',
            breed: null,
            age_description: null,
            owner_name: 'Maria Souza',
            owner_phone: null,
            owner_document: null,
            status: 'ACTIVE',
            notes: null,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
            row_version: 1,
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
      })
    }),
  )
  renderWithProviders(<PatientsPage />)

  expect(await screen.findByText('Rex')).toBeInTheDocument()

  await user.type(screen.getByLabelText('Buscar paciente'), 'joana')

  expect(await screen.findByText('Bidu')).toBeInTheDocument()
  expect(screen.queryByText('Rex')).not.toBeInTheDocument()
})

test('deactivates a patient and preserves the record', async () => {
  const user = userEvent.setup()
  let status: 'ACTIVE' | 'INACTIVE' = 'ACTIVE'
  function patientBody() {
    return {
      id: 'p1',
      name: 'Rex',
      species_id: 's1',
      sex: 'MALE',
      breed: 'SRD',
      age_description: '2 anos',
      owner_name: 'Maria Souza',
      owner_phone: null,
      owner_document: null,
      status,
      notes: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      row_version: status === 'ACTIVE' ? 1 : 2,
    }
  }
  server.use(
    meHandler(['patients.read', 'patients.manage']),
    speciesHandler(),
    patientsListHandler(),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(patientBody())),
    http.post('/api/v1/patients/p1/deactivate', () => {
      status = 'INACTIVE'
      return HttpResponse.json(patientBody())
    }),
  )
  renderWithProviders(<PatientsPage />)

  await user.click(await screen.findByText('Rex'))
  await user.click(await screen.findByRole('button', { name: 'Mais ações' }))
  await user.click(await screen.findByRole('menuitem', { name: 'Inativar' }))

  await waitFor(() => expect(screen.getByText('Inativo')).toBeInTheDocument())
})
