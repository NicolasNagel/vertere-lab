import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { PatientsPage } from './patients-page'
import { pickOption } from '../../../test/dropdown'

const server = setupServer(clinicsHandler())

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function meHandler(permissions: string[]) {
  return http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      user: {
        id: 'u1',
        email: 'a@b.com',
        full_name: 'A',
        role_id: 'r1',
        role_name: 'LAB_ADMIN',
      },
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
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>,
  )
}

function apiPatient(overrides: Record<string, unknown> = {}) {
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
    status: 'ACTIVE',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    row_version: 1,
    ...overrides,
  }
}

test('lists patients and searches by owner name, without "Novo paciente" for read-only users', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['patients.read']),
    speciesHandler(),
    http.get('/api/v1/patients', ({ request }) => {
      const search = new URL(request.url).searchParams.get('search')
      const items =
        search === 'joana'
          ? [
              apiPatient({
                id: 'p2',
                name: 'Bidu',
                species_id: 's2',
                owner_name: 'Joana Lima',
              }),
            ]
          : [apiPatient()]
      return HttpResponse.json({ items, total: 1, page: 1, page_size: 100 })
    }),
  )
  renderWithProviders(<PatientsPage />)

  expect(await screen.findByText('Rex')).toBeInTheDocument()
  expect(screen.getByText('Maria Souza')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Novo paciente/i })).not.toBeInTheDocument()

  await user.type(screen.getByLabelText('Buscar paciente'), 'joana')
  expect(await screen.findByText('Bidu')).toBeInTheDocument()
  expect(screen.queryByText('Rex')).not.toBeInTheDocument()
})

test('with patients.manage, creates a patient with embedded owner data and returns to the detail view', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['patients.read', 'patients.manage']),
    speciesHandler(),
    clinicsHandler(),
    patientsListHandler(),
    http.post('/api/v1/patients', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      return HttpResponse.json(
        apiPatient({
          id: 'p2',
          name: body.name,
          species_id: body.species_id,
          sex: body.sex,
          owner_name: body.owner_name,
        }),
        { status: 201 },
      )
    }),
    http.get('/api/v1/patients/p2', () =>
      HttpResponse.json(
        apiPatient({
          id: 'p2',
          name: 'Bidu',
          species_id: 's2',
          breed: null,
          age_description: null,
          owner_name: 'Joana Lima',
        }),
      ),
    ),
  )
  renderWithProviders(<PatientsPage />)

  await user.click(await screen.findByRole('button', { name: /Novo paciente/i }))
  await user.type(screen.getByLabelText('Nome do paciente'), 'Bidu')
  await pickOption(user, 'Clínica', 'Clínica Central')
  await pickOption(user, 'Espécie', 'Gato')
  await user.type(screen.getByLabelText('Nome do tutor'), 'Joana Lima')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: 'Novo paciente' })).not.toBeInTheDocument(),
  )
  expect(await screen.findByRole('heading', { name: 'Bidu' })).toBeInTheDocument()
  expect(screen.getByText('Joana Lima')).toBeInTheDocument()
})

test('shows an error, not the empty state, when the list request fails', async () => {
  server.use(
    meHandler(['patients.read']),
    speciesHandler(),
    http.get('/api/v1/patients', () => HttpResponse.json({}, { status: 500 })),
  )
  renderWithProviders(<PatientsPage />)

  expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível carregar os pacientes.')
  expect(screen.queryByText('Nenhum paciente encontrado.')).not.toBeInTheDocument()
})

test('a double click on Salvar creates the patient only once', async () => {
  const user = userEvent.setup()
  let posts = 0
  server.use(
    meHandler(['patients.read', 'patients.manage']),
    speciesHandler(),
    clinicsHandler(),
    patientsListHandler(),
    http.post('/api/v1/patients', async () => {
      posts += 1
      await new Promise((resolve) => setTimeout(resolve, 150))
      return HttpResponse.json(apiPatient({ id: 'p2', name: 'Bidu' }), { status: 201 })
    }),
    http.get('/api/v1/patients/p2', () => HttpResponse.json(apiPatient({ id: 'p2', name: 'Bidu' }))),
  )
  renderWithProviders(<PatientsPage />)

  await user.click(await screen.findByRole('button', { name: /Novo paciente/i }))
  await user.type(screen.getByLabelText('Nome do paciente'), 'Bidu')
  await pickOption(user, 'Clínica', 'Clínica Central')
  await pickOption(user, 'Espécie', 'Gato')
  await user.type(screen.getByLabelText('Nome do tutor'), 'Joana Lima')
  await user.dblClick(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByRole('heading', { name: 'Bidu' })).toBeInTheDocument()
  expect(posts).toBe(1)
})

test('the new patient form mirrors the API length limits instead of sending a doomed request', async () => {
  const user = userEvent.setup()
  let posts = 0
  server.use(
    meHandler(['patients.read', 'patients.manage']),
    speciesHandler(),
    clinicsHandler(),
    patientsListHandler(),
    http.post('/api/v1/patients', () => {
      posts += 1
      return HttpResponse.json(apiPatient({ id: 'p9' }), { status: 201 })
    }),
  )
  renderWithProviders(<PatientsPage />)

  await user.click(await screen.findByRole('button', { name: /Novo paciente/i }))
  await user.click(screen.getByLabelText('Nome do paciente'))
  await user.paste('N'.repeat(201))
  await pickOption(user, 'Clínica', 'Clínica Central')
  await pickOption(user, 'Espécie', 'Gato')
  await user.type(screen.getByLabelText('Nome do tutor'), 'Joana Lima')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByText('Use até 200 caracteres.')).toBeInTheDocument()
  expect(posts).toBe(0)
})

test('deactivates a patient and preserves the record', async () => {
  const user = userEvent.setup()
  let status: 'ACTIVE' | 'INACTIVE' = 'ACTIVE'
  const patientBody = () => apiPatient({ status, row_version: status === 'ACTIVE' ? 1 : 2 })
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

test('an inactive patient offers Reativar instead of Editar, and reactivating brings Editar back', async () => {
  const user = userEvent.setup()
  let status: 'ACTIVE' | 'INACTIVE' = 'INACTIVE'
  const patientBody = () => apiPatient({ status, row_version: status === 'ACTIVE' ? 3 : 2 })
  server.use(
    meHandler(['patients.read', 'patients.manage']),
    speciesHandler(),
    clinicsHandler(),
    patientsListHandler(),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(patientBody())),
    http.post('/api/v1/patients/p1/reactivate', () => {
      status = 'ACTIVE'
      return HttpResponse.json(patientBody())
    }),
  )
  renderWithProviders(<PatientsPage />)

  await user.click(await screen.findByText('Rex'))
  expect(await screen.findByRole('button', { name: 'Reativar' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Reativar' }))
  expect(await screen.findByRole('button', { name: 'Editar' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Reativar' })).not.toBeInTheDocument()
})

test('editing an existing patient does not let the clinic change (that needs a reason)', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['patients.read', 'patients.manage']),
    speciesHandler(),
    clinicsHandler(),
    patientsListHandler(),
    http.get('/api/v1/patients/p1', () =>
      HttpResponse.json(apiPatient({ clinic_id: 'c1' })),
    ),
  )
  renderWithProviders(<PatientsPage />)

  await user.click(await screen.findByText('Rex'))
  await user.click(await screen.findByRole('button', { name: 'Editar' }))

  expect(await screen.findByLabelText('Nome do paciente')).toBeEnabled()
  expect(screen.getByRole('button', { name: /Clínica/ })).toBeDisabled()
})
