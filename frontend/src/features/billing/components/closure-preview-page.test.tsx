import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { ClosurePreviewPage } from './closure-preview-page'

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
    grand_total: '100.00',
    eligible_items: [
      {
        attendance_id: 'att-1',
        attendance_exam_id: 'exam-1',
        protocol_number: '2026/000001',
        patient_name: 'Rex',
        exam_name: 'Hemograma',
        total_amount: '100.00',
      },
    ],
    blocked_items: [
      {
        attendance_id: 'att-2',
        attendance_exam_id: 'exam-2',
        protocol_number: '2026/000002',
        patient_name: 'Mia',
        exam_name: 'Urinálise',
        total_amount: '80.00',
        reason: 'Item de exame cancelado.',
      },
    ],
    generated_at: '2026-01-15T12:00:00Z',
    ...overrides,
  }
}

function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>,
  )
}

test('hides the page for a user without closures.preview', async () => {
  server.use(meHandler(['clinics.read']), clinicsListHandler())
  renderWithProviders(<ClosurePreviewPage />)

  expect(
    await screen.findByText('Você não tem permissão para visualizar a prévia de fechamento.'),
  ).toBeInTheDocument()
})

test('shows a hint before a clinic is selected', async () => {
  server.use(meHandler(['closures.preview']), clinicsListHandler())
  renderWithProviders(<ClosurePreviewPage />)

  expect(
    await screen.findByText('Selecione uma clínica para gerar a prévia da competência.'),
  ).toBeInTheDocument()
})

test('shows loading then renders eligible and blocked items with the reason visible', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    http.get('/api/v1/closures/preview', async () => {
      await delay(50)
      return HttpResponse.json(previewResponseBody())
    }),
  )
  renderWithProviders(<ClosurePreviewPage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  expect(await screen.findByText('Carregando prévia…')).toBeInTheDocument()
  expect(await screen.findByText('Rex')).toBeInTheDocument()
  expect(screen.getByText('Mia')).toBeInTheDocument()
  expect(screen.getByText('Item de exame cancelado.')).toBeInTheDocument()
  expect(screen.getByText('Elegível')).toBeInTheDocument()
  expect(screen.getByText('Bloqueado')).toBeInTheDocument()
  expect(screen.getByText('R$ 80,00')).toBeInTheDocument()
  expect(screen.getAllByText('R$ 100,00').length).toBeGreaterThan(0)
})

test('shows the empty state when there is nothing in the competence', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
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
  renderWithProviders(<ClosurePreviewPage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  expect(
    await screen.findByText('Nenhum atendimento encontrado para esta clínica e competência.'),
  ).toBeInTheDocument()
})

test('shows a generic error message on a 500 response', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    http.get('/api/v1/closures/preview', () =>
      HttpResponse.json(
        { error: { code: 'INTERNAL_ERROR', message: 'Erro interno.', details: [] } },
        { status: 500 },
      ),
    ),
  )
  renderWithProviders(<ClosurePreviewPage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  expect(
    await screen.findByText('Não foi possível carregar a prévia. Tente novamente.'),
  ).toBeInTheDocument()
})

test('shows a dedicated message on 403 instead of crashing', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    http.get('/api/v1/closures/preview', () =>
      HttpResponse.json(
        { error: { code: 'FORBIDDEN', message: 'Permissão ausente: closures.preview', details: [] } },
        { status: 403 },
      ),
    ),
  )
  renderWithProviders(<ClosurePreviewPage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  expect(
    await screen.findByText('Você não tem permissão para visualizar a prévia de fechamento.'),
  ).toBeInTheDocument()
})

test('switching clinics does not leave the previous clinic data visible during loading', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    http.get('/api/v1/closures/preview', async ({ request }) => {
      const url = new URL(request.url)
      const clinicId = url.searchParams.get('clinic_id')
      if (clinicId === 'clinic-b') {
        await delay(50)
      }
      return HttpResponse.json(
        previewResponseBody({
          clinic_id: clinicId,
          eligible_items:
            clinicId === 'clinic-a'
              ? [
                  {
                    attendance_id: 'att-1',
                    attendance_exam_id: 'exam-1',
                    protocol_number: '2026/000001',
                    patient_name: 'Rex',
                    exam_name: 'Hemograma',
                    total_amount: '100.00',
                  },
                ]
              : [],
          blocked_items: [],
        }),
      )
    }),
  )
  renderWithProviders(<ClosurePreviewPage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')
  expect(await screen.findByText('Rex')).toBeInTheDocument()

  await user.selectOptions(screen.getByLabelText('Clínica'), 'clinic-b')

  await waitFor(() => expect(screen.queryByText('Rex')).not.toBeInTheDocument())
})

test('hides the close button for a user without closures.close', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview']),
    clinicsListHandler(),
    http.get('/api/v1/closures/preview', () => HttpResponse.json(previewResponseBody())),
  )
  renderWithProviders(<ClosurePreviewPage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  await screen.findByText('Rex')
  expect(screen.queryByRole('button', { name: 'Fechar competência' })).not.toBeInTheDocument()
})

test('disables the close button when there is nothing eligible', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview', 'closures.close']),
    clinicsListHandler(),
    http.get('/api/v1/closures/preview', () =>
      HttpResponse.json(
        previewResponseBody({ item_count: 0, eligible_items: [], blocked_items: [] }),
      ),
    ),
  )
  renderWithProviders(<ClosurePreviewPage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')

  expect(await screen.findByRole('button', { name: 'Fechar competência' })).toBeDisabled()
})

test('closes the competence after explicit confirmation and shows a success banner', async () => {
  const user = userEvent.setup()
  let closedBody: Record<string, unknown> | null = null
  server.use(
    meHandler(['closures.preview', 'closures.close']),
    clinicsListHandler(),
    http.get('/api/v1/closures/preview', () => HttpResponse.json(previewResponseBody())),
    http.post('/api/v1/closures', async ({ request }) => {
      closedBody = (await request.json()) as Record<string, unknown>
      expect(request.headers.get('Idempotency-Key')).toBeTruthy()
      return HttpResponse.json(
        {
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
          grand_total: '100.00',
          generated_by: 'u1',
          closed_by: 'u1',
          generated_at: '2026-01-15T12:00:00Z',
          closed_at: '2026-01-15T12:00:00Z',
          reopened_at: null,
          version: 1,
          items: [],
        },
        { status: 201 },
      )
    }),
  )
  renderWithProviders(<ClosurePreviewPage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')
  await user.click(await screen.findByRole('button', { name: 'Fechar competência' }))

  const dialog = within(await screen.findByRole('dialog'))
  expect(dialog.getByText('Schweitzer')).toBeInTheDocument()
  // The confirm button stays disabled until the checkbox is explicitly checked.
  const confirmButton = dialog.getByRole('button', { name: 'Fechar competência' })
  expect(confirmButton).toBeDisabled()

  await user.click(dialog.getByRole('checkbox'))
  expect(confirmButton).toBeEnabled()
  await user.click(confirmButton)

  await waitFor(() => expect(closedBody).not.toBeNull())
  expect(closedBody).toMatchObject({ clinic_id: 'clinic-a', year: 2026, month: 1 })
  expect(
    await screen.findByText('Competência janeiro de 2026 fechada com sucesso — total R$ 100,00.'),
  ).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('shows a clear message when the competence was already closed', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['closures.preview', 'closures.close']),
    clinicsListHandler(),
    http.get('/api/v1/closures/preview', () => HttpResponse.json(previewResponseBody())),
    http.post('/api/v1/closures', () =>
      HttpResponse.json(
        {
          error: {
            code: 'CLOSURE_ALREADY_EXISTS',
            message: 'Já existe um fechamento ativo para esta clínica e competência.',
            details: [],
          },
        },
        { status: 409 },
      ),
    ),
  )
  renderWithProviders(<ClosurePreviewPage />)

  await user.selectOptions(await screen.findByLabelText('Clínica'), 'clinic-a')
  await user.click(await screen.findByRole('button', { name: 'Fechar competência' }))
  const dialog = within(await screen.findByRole('dialog'))
  await user.click(dialog.getByRole('checkbox'))
  await user.click(dialog.getByRole('button', { name: 'Fechar competência' }))

  expect(
    await dialog.findByText(/Já existe um fechamento ativo para esta clínica e competência\./),
  ).toBeInTheDocument()
  expect(dialog.getByText(/Recarregue a prévia/)).toBeInTheDocument()
})
