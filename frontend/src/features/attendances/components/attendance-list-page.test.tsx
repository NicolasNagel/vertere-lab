import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { AttendanceListPage } from './attendance-list-page'

const server = setupServer()

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

function veterinariansHandler() {
  return http.get('/api/v1/veterinarians', () =>
    HttpResponse.json({
      items: [
        {
          id: 'v1',
          name: 'Dra. Ana',
          crmv: 'CRMV-SC 1234',
          phone: null,
          email: null,
          is_autonomous: true,
          status: 'ACTIVE',
          notes: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
          clinics: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    }),
  )
}

function speciesHandler() {
  return http.get('/api/v1/species', () =>
    HttpResponse.json({ items: [{ id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' }] }),
  )
}

function patientsHandler() {
  return http.get('/api/v1/patients', () =>
    HttpResponse.json({
      items: [
        {
          id: 'p1',
          name: 'Bidu',
          species_id: 's1',
          sex: 'MALE',
          breed: null,
          age_description: '4 anos',
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

function attendanceItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 'a1',
    clinic_id: 'c1',
    veterinarian_id: 'v1',
    patient_id: 'p1',
    service_date: '2026-01-05',
    notes: null,
    status: 'CONFIRMED',
    items: [
      {
        id: 'ai1',
        exam_id: 'e1',
        exam_code: 'HEMO',
        exam_name: 'Hemograma',
        price_base: '100.00',
        quantity: 1,
        discount_amount: '0.00',
        surcharge_amount: '0.00',
        total_amount: '100.00',
        override_reason: null,
        status: 'ACTIVE',
      },
    ],
    billing_competence: '2026-01-01',
    subtotal: '100.00',
    discount_total: '0.00',
    surcharge_total: '0.00',
    on_call_fee: '0.00',
    grand_total: '100.00',
    protocol_number: '2026/000001',
    cancel_reason: null,
    created_at: '2026-01-05T10:00:00Z',
    updated_at: '2026-01-05T10:00:00Z',
    row_version: 2,
    ...overrides,
  }
}

function attendancesHandler(items: Record<string, unknown>[]) {
  return http.get('/api/v1/attendances', () =>
    HttpResponse.json({ items, total: items.length, page: 1, page_size: 20 }),
  )
}

function statusCountsHandler(byStatus: Record<string, number> = { CONFIRMED: 1, CANCELLED: 1 }) {
  return http.get('/api/v1/attendances/status-counts', () =>
    HttpResponse.json({
      total: Object.values(byStatus).reduce((sum, count) => sum + count, 0),
      by_status: byStatus,
    }),
  )
}

function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('lists attendances with resolved clinic/veterinarian/patient names', async () => {
  server.use(
    meHandler(['attendances.read']),
    clinicsHandler(),
    veterinariansHandler(),
    speciesHandler(),
    patientsHandler(),
    statusCountsHandler(),
    attendancesHandler([
      attendanceItem({ service_date: '2026-07-05', created_at: '2026-08-01T10:00:00Z' }),
    ]),
  )
  renderWithProviders(<AttendanceListPage />)

  expect(await screen.findByText('2026/000001')).toBeInTheDocument()
  expect(screen.getByText('Data · Hora')).toBeInTheDocument()
  expect(screen.getByText(/05\/07 · \d{2}:00/)).toBeInTheDocument()
  expect(screen.getByLabelText('Competência')).toBeInTheDocument()
  expect(screen.queryByLabelText('Mês')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Ano')).not.toBeInTheDocument()
  const dataRow = within(screen.getByRole('row'))
  expect(dataRow.getByText('Clínica Central')).toBeInTheDocument()
  expect(dataRow.getByText('Dra. Ana')).toBeInTheDocument()
  expect(dataRow.getByText('Bidu')).toBeInTheDocument()
  expect(dataRow.getByText(/4 anos/)).toBeInTheDocument()
  expect(dataRow.getByText('Hemograma')).toBeInTheDocument()
  expect(dataRow.getByText('R$ 100,00')).toBeInTheDocument()
})

test('shows a permission-denied message for a user without attendances.read', async () => {
  server.use(meHandler([]), clinicsHandler(), veterinariansHandler(), speciesHandler(), patientsHandler())
  renderWithProviders(<AttendanceListPage />)

  expect(
    await screen.findByText('Você não tem permissão para visualizar atendimentos.'),
  ).toBeInTheDocument()
})

test('shows the empty state when there are no attendances for the filters', async () => {
  server.use(
    meHandler(['attendances.read']),
    clinicsHandler(),
    veterinariansHandler(),
    speciesHandler(),
    patientsHandler(),
    statusCountsHandler(),
    attendancesHandler([]),
  )
  renderWithProviders(<AttendanceListPage />)

  expect(
    await screen.findByText('Nenhum atendimento encontrado para os filtros selecionados.'),
  ).toBeInTheDocument()
})

test('shows a draft attendance without a protocol number or total', async () => {
  server.use(
    meHandler(['attendances.read']),
    clinicsHandler(),
    veterinariansHandler(),
    speciesHandler(),
    patientsHandler(),
    statusCountsHandler(),
    attendancesHandler([
      attendanceItem({
        status: 'DRAFT',
        items: [],
        protocol_number: null,
        grand_total: '0.00',
      }),
    ]),
  )
  renderWithProviders(<AttendanceListPage />)

  const dashes = await screen.findAllByText('—')
  expect(dashes.length).toBeGreaterThan(0)
  expect(screen.getAllByText('Rascunho').length).toBeGreaterThan(1) // filtro + linha/status
})

test('re-filters by status and resets to page 1', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['attendances.read']),
    clinicsHandler(),
    veterinariansHandler(),
    speciesHandler(),
    patientsHandler(),
    statusCountsHandler(),
    http.get('/api/v1/attendances', ({ request }) => {
      const url = new URL(request.url)
      const status = url.searchParams.get('status')
      const items = status === 'CANCELLED' ? [] : [attendanceItem()]
      return HttpResponse.json({ items, total: items.length, page: 1, page_size: 20 })
    }),
  )
  renderWithProviders(<AttendanceListPage />)

  expect(await screen.findByText('2026/000001')).toBeInTheDocument()

  await user.click(screen.getByRole('tab', { name: /Cancelado/ }))

  await waitFor(() =>
    expect(
      screen.getByText('Nenhum atendimento encontrado para os filtros selecionados.'),
    ).toBeInTheDocument(),
  )
})
