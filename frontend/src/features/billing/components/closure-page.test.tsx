import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { ClosurePage } from './closure-page'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function meHandler(permissions: string[]) {
  return http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      user: {
        id: 'u1',
        email: 'finance@vertere.local',
        full_name: 'Finance',
        role_id: 'r1',
        role_name: 'FINANCE',
      },
      permissions,
    }),
  )
}

function clinicsListHandler() {
  return http.get('/api/v1/clinics', () =>
    HttpResponse.json({
      items: [
        { id: 'clinic-a', name: 'Schweitzer', status: 'ACTIVE', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', row_version: 1 },
        { id: 'clinic-b', name: 'VetCenter', status: 'ACTIVE', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', row_version: 1 },
      ],
      total: 2,
      page: 1,
      page_size: 100,
    }),
  )
}

function clinicDetailHandler() {
  return http.get('/api/v1/clinics/:id', ({ params }) =>
    HttpResponse.json({
      id: params.id,
      name: params.id === 'clinic-a' ? 'Schweitzer' : 'VetCenter',
      tax_id: '78977352000199',
      phone: null,
      email: null,
      status: 'ACTIVE',
      address_zip_code: null,
      address_street: null,
      address_number: null,
      address_neighborhood: null,
      address_city: null,
      address_state: null,
      address_complement: null,
      notes: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      row_version: 1,
      veterinarians: [],
    }),
  )
}

function byPeriodNotFoundHandler() {
  return http.get('/api/v1/closures/by-period', () =>
    HttpResponse.json(
      { error: { code: 'NOT_FOUND', message: 'Nenhum fechamento encontrado.', details: [] } },
      { status: 404 },
    ),
  )
}

function previewResponseBody(overrides: Record<string, unknown> = {}) {
  return {
    clinic_id: 'clinic-a',
    competence_year: 2026,
    competence_month: 1,
    period_start: '2026-01-01',
    period_end: '2026-01-31',
    attendance_count: 2,
    cancelled_attendance_count: 0,
    item_count: 1,
    subtotal: '100.00',
    discount_total: '0.00',
    surcharge_total: '0.00',
    on_call_fee_total: '0.00',
    grand_total: '100.00',
    eligible_items: [
      {
        attendance_id: 'att-1',
        attendance_exam_id: 'exam-1',
        protocol_number: 'P000001/26',
        patient_name: 'Rex',
        exam_name: 'Hemograma',
        service_level: 'NORMAL',
        exam_category: 'Hematológico',
        total_amount: '100.00',
      },
    ],
    blocked_items: [
      {
        attendance_id: 'att-2',
        attendance_exam_id: 'exam-2',
        protocol_number: 'P000002/26',
        patient_name: 'Mia',
        exam_name: 'Urinálise',
        service_level: 'NORMAL',
        exam_category: 'Urinário',
        total_amount: '80.00',
        reason: 'Item de exame cancelado.',
      },
    ],
    generated_at: '2026-01-15T12:00:00Z',
    ...overrides,
  }
}

function closureResponseBody(overrides: Record<string, unknown> = {}) {
  return {
    id: 'closure-1',
    clinic_id: 'clinic-a',
    competence_year: 2026,
    competence_month: 1,
    period_start: '2026-01-01',
    period_end: '2026-01-31',
    status: 'CLOSED',
    item_count: 1,
    subtotal: '100.00',
    discount_total: '0.00',
    surcharge_total: '0.00',
    on_call_fee_total: '0.00',
    grand_total: '100.00',
    generated_by: 'u1',
    closed_by: 'u1',
    generated_at: '2026-01-15T12:00:00Z',
    closed_at: '2026-01-15T12:00:00Z',
    reopened_at: null,
    version: 1,
    items: [
      {
        id: 'item-1',
        attendance_id: 'att-1',
        attendance_exam_id: 'exam-1',
        protocol_number: 'P000001/26',
        patient_name: 'Rex',
        exam_name: 'Hemograma',
        price_base: '100.00',
        quantity: 1,
        discount_amount: '0.00',
        surcharge_amount: '0.00',
        total_amount: '100.00',
        service_level: 'NORMAL',
        exam_category: 'Hematológico',
      },
    ],
    adjustments: [],
    ...overrides,
  }
}

function renderWithProviders(children: ReactNode, initialEntry = '/financeiro/fechamento') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('hides the page for a user without closures.read or closures.preview', async () => {
  server.use(meHandler(['clinics.read']), clinicsListHandler())
  renderWithProviders(<ClosurePage />)

  expect(
    await screen.findByText('Você não tem permissão para visualizar fechamentos.'),
  ).toBeInTheDocument()
})

test('shows a plain hint before a clinic is selected for a user without closures.read', async () => {
  server.use(meHandler(['closures.preview']), clinicsListHandler())
  renderWithProviders(<ClosurePage />)

  expect(
    await screen.findByText('Selecione uma clínica para gerar a prévia do período.'),
  ).toBeInTheDocument()
})

test('shows the closures history instead of a hint when the user has closures.read', async () => {
  server.use(
    meHandler(['closures.read']),
    clinicsListHandler(),
    http.get('/api/v1/closures', () =>
      HttpResponse.json({
        items: [
          {
            id: 'closure-1',
            clinic_id: 'clinic-a',
            competence_year: 2026,
            competence_month: 1,
            period_start: '2026-01-01',
            period_end: '2026-01-31',
            status: 'CLOSED',
            item_count: 1,
            grand_total: '100.00',
            closed_by: 'u1',
            closed_at: '2026-01-15T12:00:00Z',
            version: 1,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    ),
  )
  renderWithProviders(<ClosurePage />)

  expect(
    screen.queryByText('Selecione uma clínica para gerar a prévia do período.'),
  ).not.toBeInTheDocument()
  expect(await screen.findByText('01 de jan. de 2026 – 31 de jan. de 2026')).toBeInTheDocument()
})

test('clicking a row in the closures history navigates into its detail', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.read', 'closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures', () =>
      HttpResponse.json({
        items: [
          {
            id: 'closure-1',
            clinic_id: 'clinic-a',
            competence_year: 2026,
            competence_month: 1,
            period_start: '2026-01-01',
            period_end: '2026-01-31',
            status: 'CLOSED',
            item_count: 1,
            grand_total: '100.00',
            closed_by: 'u1',
            closed_at: '2026-01-15T12:00:00Z',
            version: 1,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    ),
    http.get('/api/v1/closures/by-period', () => HttpResponse.json(closureResponseBody())),
  )
  renderWithProviders(<ClosurePage />)

  await user.click(await screen.findByText('01 de jan. de 2026 – 31 de jan. de 2026'))

  expect(await screen.findByText('Fechado')).toBeInTheDocument()
})

test('shows the prévia when the user only has closures.preview', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/preview', async () => {
      await delay(50)
      return HttpResponse.json(previewResponseBody())
    }),
  )
  renderWithProviders(<ClosurePage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  expect(await screen.findByText('Carregando prévia…')).toBeInTheDocument()
  expect(await screen.findByText('Rex')).toBeInTheDocument()
  expect(screen.getByText('Mia')).toBeInTheDocument()
  expect(screen.getByText('Item de exame cancelado.')).toBeInTheDocument()
})

test('shows the empty state when there is nothing in the period', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/preview', () =>
      HttpResponse.json(
        previewResponseBody({
          attendance_count: 0,
          item_count: 0,
          subtotal: '0.00',
          grand_total: '0.00',
          eligible_items: [],
          blocked_items: [],
        }),
      ),
    ),
  )
  renderWithProviders(<ClosurePage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  expect(
    await screen.findByText('Nenhum atendimento encontrado para esta clínica e período.'),
  ).toBeInTheDocument()
})

test('shows a dedicated message on a 403 instead of crashing', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/preview', () =>
      HttpResponse.json(
        { error: { code: 'FORBIDDEN', message: 'Permissão ausente: closures.preview', details: [] } },
        { status: 403 },
      ),
    ),
  )
  renderWithProviders(<ClosurePage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  expect(
    await screen.findByText('Você não tem permissão para visualizar a prévia de fechamento.'),
  ).toBeInTheDocument()
})

test('checks for an existing closure first when the user has closures.read', async () => {
  const user = userEvent.setup()
  let previewRequested = false
  server.use(
    meHandler(['closures.read', 'closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    byPeriodNotFoundHandler(),
    http.get('/api/v1/closures/preview', () => {
      previewRequested = true
      return HttpResponse.json(previewResponseBody())
    }),
  )
  renderWithProviders(<ClosurePage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  expect(await screen.findByText('Rex')).toBeInTheDocument()
  expect(previewRequested).toBe(true)
})

test('renders the existing closure instead of the prévia when one is found', async () => {
  server.use(
    meHandler(['closures.read', 'closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/by-period', () => HttpResponse.json(closureResponseBody())),
  )
  renderWithProviders(
    <ClosurePage />,
    '/financeiro/fechamento?clinicId=clinic-a&periodStart=2026-01-01&periodEnd=2026-01-31',
  )

  expect(await screen.findByText('Fechado')).toBeInTheDocument()
  expect(screen.getByText('Rex')).toBeInTheDocument()
  expect(screen.queryByText('Carregando prévia…')).not.toBeInTheDocument()
})

test('a reopened closure is shown alongside a fresh prévia so it can be closed again', async () => {
  server.use(
    meHandler(['closures.read', 'closures.preview', 'closures.close']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/by-period', () =>
      HttpResponse.json(closureResponseBody({ status: 'REOPENED', reopened_at: '2026-02-01T00:00:00Z' })),
    ),
    http.get('/api/v1/closures/preview', () => HttpResponse.json(previewResponseBody())),
  )
  renderWithProviders(
    <ClosurePage />,
    '/financeiro/fechamento?clinicId=clinic-a&periodStart=2026-01-01&periodEnd=2026-01-31',
  )

  // The reaberto record stays visible as history...
  expect(await screen.findByText('Reaberto')).toBeInTheDocument()
  // ...but a fresh prévia (and the close action) is offered too, otherwise
  // there would be no way to close the período again.
  expect(await screen.findByRole('button', { name: 'Fechar período' })).toBeInTheDocument()
})

test('hides the close button for a user without closures.close', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/preview', () => HttpResponse.json(previewResponseBody())),
  )
  renderWithProviders(<ClosurePage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  await screen.findByText('Rex')
  expect(screen.queryByRole('button', { name: 'Fechar período' })).not.toBeInTheDocument()
})

test('closes the period after explicit confirmation and shows a success banner', async () => {
  const user = userEvent.setup()
  let closedBody: Record<string, unknown> | null = null
  server.use(
    meHandler(['closures.preview', 'closures.close']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/preview', () => HttpResponse.json(previewResponseBody())),
    http.post('/api/v1/closures', async ({ request }) => {
      closedBody = (await request.json()) as Record<string, unknown>
      return HttpResponse.json(closureResponseBody({ items: [] }), { status: 201 })
    }),
  )
  renderWithProviders(<ClosurePage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')
  await user.click(await screen.findByRole('button', { name: 'Fechar período' }))

  const dialog = within(await screen.findByRole('dialog'))
  await user.click(dialog.getByRole('checkbox'))
  await user.dblClick(dialog.getByRole('button', { name: 'Fechar período' }))

  await waitFor(() => expect(closedBody).not.toBeNull())
  expect(closedBody).toMatchObject({
    clinic_id: 'clinic-a',
    period_start: '2026-01-01',
    period_end: '2026-01-31',
  })
  expect(
    await screen.findByText(
      'Período 01 de jan. de 2026 – 31 de jan. de 2026 fechado com sucesso — total R$ 100,00.',
    ),
  ).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('switching clinics does not leave the previous clinic data visible during loading', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/preview', async ({ request }) => {
      const url = new URL(request.url)
      const clinicId = url.searchParams.get('clinic_id')
      if (clinicId === 'clinic-b') {
        await delay(50)
      }
      return HttpResponse.json(
        previewResponseBody({
          clinic_id: clinicId,
          eligible_items: clinicId === 'clinic-a' ? previewResponseBody().eligible_items : [],
          blocked_items: [],
        }),
      )
    }),
  )
  renderWithProviders(<ClosurePage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')
  expect(await screen.findByText('Rex')).toBeInTheDocument()

  await user.selectOptions(screen.getByLabelText('Clínica'), 'clinic-b')

  await waitFor(() => expect(screen.queryByText('Rex')).not.toBeInTheDocument())
})

test('the demonstrativo panel shows the CNPJ and the category breakdown of the prévia', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/preview', () => HttpResponse.json(previewResponseBody())),
  )
  renderWithProviders(<ClosurePage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  expect(await screen.findByText('78.977.352/0001-99')).toBeInTheDocument()
  expect(screen.getByText('Hematológico · 1')).toBeInTheDocument()
})

test('the demonstrativo panel reflects the closed fechamento when one already exists', async () => {
  server.use(
    meHandler(['closures.read', 'closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/by-period', () => HttpResponse.json(closureResponseBody())),
  )
  renderWithProviders(
    <ClosurePage />,
    '/financeiro/fechamento?clinicId=clinic-a&periodStart=2026-01-01&periodEnd=2026-01-31',
  )

  expect(await screen.findByText('78.977.352/0001-99')).toBeInTheDocument()
  expect(screen.getByText('Hematológico · 1')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Baixar CSV do fechamento' })).toHaveAttribute(
    'href',
    '/api/v1/closures/closure-1/export',
  )
})

test('toggling to "Por protocolo" groups the eligible items by atendimento', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    clinicDetailHandler(),
    http.get('/api/v1/closures/preview', () =>
      HttpResponse.json(
        previewResponseBody({
          eligible_items: [
            {
              attendance_id: 'att-1',
              attendance_exam_id: 'exam-1',
              protocol_number: 'P000001/26',
              patient_name: 'Rex',
              exam_name: 'Hemograma',
              service_level: 'NORMAL',
              exam_category: 'Hematológico',
              total_amount: '75.00',
            },
            {
              attendance_id: 'att-1',
              attendance_exam_id: 'exam-2',
              protocol_number: 'P000001/26',
              patient_name: 'Rex',
              exam_name: 'Bioquímico renal',
              service_level: 'NORMAL',
              exam_category: 'Bioquímico',
              total_amount: '120.00',
            },
          ],
        }),
      ),
    ),
  )
  renderWithProviders(<ClosurePage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')
  await screen.findByText('Hemograma')

  await user.click(screen.getByRole('button', { name: 'Por protocolo' }))

  expect(await screen.findByText('Hemograma, Bioquímico renal')).toBeInTheDocument()
  expect(screen.getByText('R$ 195,00')).toBeInTheDocument()
})
