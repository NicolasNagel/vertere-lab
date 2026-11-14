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
    HttpResponse.json({
      items: [{ id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' }],
    }),
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
    protocol_number: 'P000001/26',
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
      billed_total: '0.00',
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

test('lists attendances with resolved names, shows drafts without protocol or total and gates by permission', async () => {
  const lookups = [clinicsHandler(), veterinariansHandler(), speciesHandler(), patientsHandler()]

  // Sem attendances.read.
  server.use(meHandler([]), ...lookups)
  let view = renderWithProviders(<AttendanceListPage />)
  expect(
    await screen.findByText('Você não tem permissão para visualizar atendimentos.'),
  ).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  // Confirmado: nomes resolvidos de clínica, veterinário e paciente.
  server.use(
    meHandler(['attendances.read']),
    ...lookups,
    statusCountsHandler(),
    attendancesHandler([
      attendanceItem({ service_date: '2026-07-05', created_at: '2026-08-01T10:00:00Z' }),
    ]),
  )
  view = renderWithProviders(<AttendanceListPage />)
  expect(await screen.findByText('P000001/26')).toBeInTheDocument()
  expect(screen.getByText('Data · Hora')).toBeInTheDocument()
  expect(screen.getByText(/05\/07 · \d{2}:00/)).toBeInTheDocument()
  expect(screen.getByLabelText('Competência')).toBeInTheDocument()
  expect(screen.queryByLabelText('Mês')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Ano')).not.toBeInTheDocument()
  // A tabela agora é um <table> real: a primeira linha é o cabeçalho.
  const dataRow = within(screen.getAllByRole('row')[1] as HTMLElement)
  expect(dataRow.getByText('Clínica Central')).toBeInTheDocument()
  expect(dataRow.getByText('Dra. Ana')).toBeInTheDocument()
  expect(dataRow.getByText('Bidu')).toBeInTheDocument()
  expect(dataRow.getByText(/4 anos/)).toBeInTheDocument()
  expect(dataRow.getByText('Hemograma')).toBeInTheDocument()
  expect(dataRow.getByText('R$ 100,00')).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  // Rascunho: sem protocolo nem total.
  server.use(
    meHandler(['attendances.read']),
    ...lookups,
    statusCountsHandler(),
    attendancesHandler([
      attendanceItem({ status: 'DRAFT', items: [], protocol_number: null, grand_total: '0.00' }),
    ]),
  )
  renderWithProviders(<AttendanceListPage />)
  const draftRow = within((await screen.findAllByRole('row'))[1] as HTMLElement)
  expect(draftRow.getAllByText('Rascunho')).toHaveLength(2) // protocolo + status
  expect(draftRow.getByText('—', { selector: 'td' })).toBeInTheDocument() // sem total
})

test('re-filtering by status resets to page 1 and shows the empty state when nothing matches', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['attendances.read']),
    clinicsHandler(),
    veterinariansHandler(),
    speciesHandler(),
    patientsHandler(),
    statusCountsHandler(),
    http.get('/api/v1/attendances', ({ request }) => {
      const status = new URL(request.url).searchParams.get('status')
      const items = status === 'CANCELLED' ? [] : [attendanceItem()]
      return HttpResponse.json({ items, total: items.length, page: 1, page_size: 20 })
    }),
  )
  renderWithProviders(<AttendanceListPage />)

  expect(await screen.findByText('P000001/26')).toBeInTheDocument()
  await user.click(screen.getByRole('tab', { name: /Cancelado/ }))

  await waitFor(() =>
    expect(
      screen.getByText('Nenhum atendimento encontrado para os filtros selecionados.'),
    ).toBeInTheDocument(),
  )
})

test('debounces the protocol search and warns when a name lookup fails', async () => {
  const user = userEvent.setup()
  const searches: (string | null)[] = []
  server.use(
    meHandler(['attendances.read']),
    clinicsHandler(),
    veterinariansHandler(),
    speciesHandler(),
    statusCountsHandler(),
    http.get('/api/v1/patients', () => HttpResponse.json({}, { status: 500 })),
    http.get('/api/v1/attendances', ({ request }) => {
      searches.push(new URL(request.url).searchParams.get('protocol_number'))
      return HttpResponse.json({
        items: [attendanceItem()],
        total: 1,
        page: 1,
        page_size: 20,
      })
    }),
  )
  renderWithProviders(<AttendanceListPage />)

  // Falha ao carregar pacientes não some em silêncio: a lista segue e avisa.
  expect(await screen.findByText('P000001/26')).toBeInTheDocument()
  expect(
    await screen.findByText(
      /Não foi possível carregar nomes de clínicas, veterinários ou pacientes/,
    ),
  ).toBeInTheDocument()

  // Uma digitação rápida gera uma única busca com o texto final, não uma por tecla.
  await user.type(screen.getByPlaceholderText('Buscar protocolo...'), 'P0000')
  await waitFor(() => expect(searches.at(-1)).toBe('P0000'))
  expect(searches.filter((value) => value !== null)).toEqual(['P0000'])
})
