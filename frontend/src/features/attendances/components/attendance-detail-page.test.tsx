import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { AttendanceDetailPage } from './attendance-detail-page'

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

function draftAttendance(overrides: Record<string, unknown> = {}) {
  return {
    id: 'a1',
    clinic_id: 'c1',
    veterinarian_id: 'v1',
    patient_id: 'p1',
    service_date: '2026-01-05',
    notes: null,
    status: 'DRAFT',
    items: [],
    billing_competence: null,
    subtotal: '0.00',
    discount_total: '0.00',
    surcharge_total: '0.00',
    grand_total: '0.00',
    protocol_number: null,
    cancel_reason: null,
    created_at: '2026-01-05T10:00:00Z',
    updated_at: '2026-01-05T10:00:00Z',
    row_version: 1,
    ...overrides,
  }
}

function attendanceHandler(body: Record<string, unknown>) {
  return http.get('/api/v1/attendances/a1', () => HttpResponse.json(body))
}

function clinic() {
  return {
    id: 'c1',
    name: 'Clínica Central',
    tax_id: null,
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
  }
}

function clinicNorte() {
  return { ...clinic(), id: 'c2', name: 'Clínica Norte' }
}

function veterinarian() {
  return {
    id: 'v1',
    name: 'Dra. Ana',
    crmv: 'CRMV-SC 0001',
    phone: null,
    email: null,
    is_autonomous: true,
    status: 'ACTIVE',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    row_version: 1,
    clinics: [],
  }
}

function veterinarianBruno() {
  return { ...veterinarian(), id: 'v2', name: 'Dr. Bruno', is_autonomous: false }
}

function patient() {
  return {
    id: 'p1',
    name: 'Bidu',
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
  }
}

function patientThor() {
  return { ...patient(), id: 'p2', name: 'Thor', owner_name: 'Marcelo Andrade' }
}

function headerDetailsHandlers() {
  return [
    http.get('/api/v1/clinics/c1', () => HttpResponse.json(clinic())),
    http.get('/api/v1/clinics/c2', () => HttpResponse.json(clinicNorte())),
    http.get('/api/v1/veterinarians/v1', () => HttpResponse.json(veterinarian())),
    http.get('/api/v1/veterinarians/v2', () => HttpResponse.json(veterinarianBruno())),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(patient())),
    http.get('/api/v1/patients/p2', () => HttpResponse.json(patientThor())),
    http.get('/api/v1/clinics', () =>
      HttpResponse.json({ items: [clinic(), clinicNorte()], total: 2, page: 1, page_size: 100 }),
    ),
    http.get('/api/v1/veterinarians', ({ request }) => {
      const url = new URL(request.url)
      const availableForClinicId = url.searchParams.get('available_for_clinic_id')
      const items =
        !availableForClinicId || availableForClinicId === 'c1'
          ? [veterinarian(), veterinarianBruno()]
          : [veterinarian()]
      return HttpResponse.json({ items, total: items.length, page: 1, page_size: 100 })
    }),
    http.get('/api/v1/patients', ({ request }) => {
      const url = new URL(request.url)
      const search = url.searchParams.get('search')
      const items = search?.toLowerCase().includes('thor') ? [patientThor()] : []
      return HttpResponse.json({ items, total: items.length, page: 1, page_size: 10 })
    }),
  ]
}

function examSearchHandler(matches: Record<string, unknown>[]) {
  return http.get('/api/v1/exams', ({ request }) => {
    const url = new URL(request.url)
    const search = url.searchParams.get('search')
    const items = search ? matches : []
    return HttpResponse.json({ items, total: items.length, page: 1, page_size: 10 })
  })
}

function hemograma() {
  return {
    id: 'e1',
    code: 'HEMO',
    name: 'Hemograma',
    category_id: 'cat1',
    description: null,
    species_ids: [],
    status: 'ACTIVE',
    row_version: 1,
    price_base: '100.00',
    plantao_surcharge_fixed: null,
    plantao_surcharge_percent: null,
    updated_at: '2026-01-01T00:00:00Z',
  }
}

function timelineEntry(overrides: Record<string, unknown> = {}) {
  return {
    id: 't1',
    occurred_at: '2026-01-05T10:05:00Z',
    actor_user_id: 'u1',
    action: 'attendances.confirmed',
    before_state: null,
    after_state: null,
    reason: null,
    ...overrides,
  }
}

function timelineHandler(items: Record<string, unknown>[]) {
  return http.get('/api/v1/attendances/a1/timeline', () =>
    HttpResponse.json({ items, total: items.length, page: 1, page_size: 20 }),
  )
}

function previewHandler(items: Record<string, unknown>[]) {
  return http.post('/api/v1/attendances/a1/preview', async () =>
    HttpResponse.json({
      attendance_id: 'a1',
      clinic_id: 'c1',
      veterinarian_id: 'v1',
      patient_id: 'p1',
      service_date: '2026-01-05',
      items,
      subtotal: '200.00',
      discount_total: '0.00',
      surcharge_total: '0.00',
      grand_total: '200.00',
    }),
  )
}

function renderPage(permissions: string[], handlers: ReturnType<typeof http.get>[] = []) {
  server.use(...handlers, meHandler(permissions))
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={['/operacao/a1']}>
          <Routes>
            <Route path="/operacao/:attendanceId" element={<AttendanceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('shows a permission-denied message for a user without attendances.read', async () => {
  renderPage([], [attendanceHandler(draftAttendance())])

  expect(
    await screen.findByText('Você não tem permissão para visualizar atendimentos.'),
  ).toBeInTheDocument()
})

test('shows a not-found message for an unknown attendance', async () => {
  server.use(
    http.get('/api/v1/attendances/a1', () =>
      HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'Não encontrado.' } }, { status: 404 }),
    ),
  )
  renderPage(['attendances.read'])

  expect(await screen.findByText('Atendimento não encontrado.')).toBeInTheDocument()
})

test('shows the read-only view for a non-draft attendance', async () => {
  renderPage(
    ['attendances.read'],
    [
      attendanceHandler(
        draftAttendance({
          status: 'CONFIRMED',
          protocol_number: '2026/000001',
          items: [
            {
              id: 'i1',
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
          subtotal: '100.00',
          grand_total: '100.00',
        }),
      ),
      http.get('/api/v1/exams/e1', () => HttpResponse.json(hemograma())),
      http.get('/api/v1/exam-categories/cat1', () =>
        HttpResponse.json({ id: 'cat1', name: 'Hematológico', status: 'ACTIVE', row_version: 1 }),
      ),
    ],
  )

  expect(await screen.findByText('2026/000001')).toBeInTheDocument()
  expect(screen.getAllByText('Hemograma').length).toBeGreaterThan(0)
  expect(await screen.findByText('Hematológico')).toBeInTheDocument()
  expect(document.querySelector('.attendance-readonly-detail__total-value')).toHaveTextContent(
    'R$ 100,00',
  )
  expect(screen.queryByRole('button', { name: 'Confirmar atendimento' })).not.toBeInTheDocument()
})

test('adds an exam, shows the backend-computed preview total, and confirms', async () => {
  const user = userEvent.setup()
  let confirmedBody: Record<string, unknown> | null = null
  let currentAttendance = draftAttendance()
  const confirmedAttendance = draftAttendance({
    status: 'CONFIRMED',
    protocol_number: '2026/000001',
    items: [
      {
        id: 'i1',
        exam_id: 'e1',
        exam_code: 'HEMO',
        exam_name: 'Hemograma',
        price_base: '100.00',
        quantity: 2,
        discount_amount: '0.00',
        surcharge_amount: '0.00',
        total_amount: '200.00',
        override_reason: null,
        status: 'ACTIVE',
      },
    ],
    subtotal: '200.00',
    grand_total: '200.00',
  })
  server.use(
    http.get('/api/v1/attendances/a1', () => HttpResponse.json(currentAttendance)),
    examSearchHandler([hemograma()]),
    previewHandler([
      {
        id: 'preview-1',
        exam_id: 'e1',
        exam_code: 'HEMO',
        exam_name: 'Hemograma',
        price_base: '100.00',
        quantity: 2,
        discount_amount: '0.00',
        surcharge_amount: '0.00',
        total_amount: '200.00',
        override_reason: null,
        status: 'ACTIVE',
      },
    ]),
    http.post('/api/v1/attendances/a1/confirm', async ({ request }) => {
      confirmedBody = (await request.json()) as Record<string, unknown>
      expect(request.headers.get('Idempotency-Key')).toBeTruthy()
      currentAttendance = confirmedAttendance
      return HttpResponse.json(confirmedAttendance)
    }),
  )
  renderPage(['attendances.read', 'attendances.update'])

  await user.type(await screen.findByLabelText('Adicionar exame'), 'Hemo')
  await user.click(await screen.findByRole('option', { name: /Hemograma/ }))

  const quantityInput = await screen.findByLabelText('Quantidade')
  fireEvent.change(quantityInput, { target: { value: '2' } })

  await waitFor(
    () =>
      expect(document.querySelector('.attendance-summary-panel__total-value')).toHaveTextContent(
        'R$ 200,00',
      ),
    { timeout: 3000 },
  )

  await user.click(screen.getByRole('button', { name: 'Confirmar atendimento' }))

  await waitFor(() => expect(confirmedBody).not.toBeNull())
  expect(confirmedBody).toMatchObject({ items: [{ exam_id: 'e1', quantity: 2 }] })
  expect(await screen.findByText('2026/000001')).toBeInTheDocument()
})

test('confirm button is disabled without any exam selected', async () => {
  renderPage(['attendances.read', 'attendances.update'], [attendanceHandler(draftAttendance())])

  expect(await screen.findByRole('button', { name: 'Confirmar atendimento' })).toBeDisabled()
})

test('hides the discount field for a user without attendances.override_price', async () => {
  const user = userEvent.setup()
  server.use(
    attendanceHandler(draftAttendance()),
    examSearchHandler([hemograma()]),
    previewHandler([]),
  )
  renderPage(['attendances.read', 'attendances.update'])

  await user.type(await screen.findByLabelText('Adicionar exame'), 'Hemo')
  await user.click(await screen.findByRole('option', { name: /Hemograma/ }))

  await screen.findByLabelText('Quantidade')
  expect(screen.queryByLabelText('Desconto (R$)')).not.toBeInTheDocument()
})

test('cancels a DRAFT attendance from the detail page', async () => {
  const user = userEvent.setup()
  let cancelledBody: Record<string, unknown> | null = null
  let currentAttendance = draftAttendance()
  const cancelledAttendance = draftAttendance({ status: 'CANCELLED', cancel_reason: 'Pedido do tutor' })
  server.use(
    http.get('/api/v1/attendances/a1', () => HttpResponse.json(currentAttendance)),
    timelineHandler([]),
    http.post('/api/v1/attendances/a1/cancel', async ({ request }) => {
      cancelledBody = (await request.json()) as Record<string, unknown>
      currentAttendance = cancelledAttendance
      return HttpResponse.json(cancelledAttendance)
    }),
  )
  renderPage(['attendances.read', 'attendances.update', 'attendances.cancel'])

  await user.click(await screen.findByRole('button', { name: 'Cancelar atendimento' }))
  await user.type(await screen.findByLabelText('Motivo do cancelamento'), 'Pedido do tutor')
  await user.click(screen.getByRole('button', { name: 'Confirmar cancelamento' }))

  await waitFor(() => expect(cancelledBody).not.toBeNull())
  expect(cancelledBody).toMatchObject({ reason: 'Pedido do tutor' })
  expect(await screen.findByText('Motivo do cancelamento: Pedido do tutor')).toBeInTheDocument()
})

test('the cancel button requires a non-empty reason before submitting', async () => {
  const user = userEvent.setup()
  renderPage(
    ['attendances.read', 'attendances.cancel'],
    [attendanceHandler(draftAttendance()), timelineHandler([])],
  )

  await user.click(await screen.findByRole('button', { name: 'Cancelar atendimento' }))
  expect(screen.getByRole('button', { name: 'Confirmar cancelamento' })).toBeDisabled()
})

test('hides the cancel button for a user without attendances.cancel', async () => {
  renderPage(
    ['attendances.read', 'attendances.update'],
    [attendanceHandler(draftAttendance()), timelineHandler([])],
  )

  await screen.findByLabelText('Adicionar exame')
  expect(screen.queryByRole('button', { name: 'Cancelar atendimento' })).not.toBeInTheDocument()
})

test('hides the cancel button once the attendance is already cancelled', async () => {
  renderPage(
    ['attendances.read', 'attendances.cancel'],
    [attendanceHandler(draftAttendance({ status: 'CANCELLED', cancel_reason: 'x' })), timelineHandler([])],
  )

  await screen.findByText('Cancelado')
  expect(screen.queryByRole('button', { name: 'Cancelar atendimento' })).not.toBeInTheDocument()
})

test('edits the notes of a CONFIRMED attendance', async () => {
  const user = userEvent.setup()
  let updatedBody: Record<string, unknown> | null = null
  let currentAttendance = draftAttendance({
    status: 'CONFIRMED',
    protocol_number: '2026/000001',
    notes: 'Observação original',
    row_version: 2,
  })
  server.use(
    http.get('/api/v1/attendances/a1', () => HttpResponse.json(currentAttendance)),
    timelineHandler([]),
    http.patch('/api/v1/attendances/a1', async ({ request }) => {
      updatedBody = (await request.json()) as Record<string, unknown>
      currentAttendance = draftAttendance({
        status: 'CONFIRMED',
        protocol_number: '2026/000001',
        notes: 'Nova observação',
        row_version: 3,
      })
      return HttpResponse.json(currentAttendance)
    }),
  )
  renderPage(['attendances.read', 'attendances.update'])

  expect(await screen.findByText('Observação original')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Editar' }))

  const notesInput = screen.getByLabelText('Observações')
  await user.clear(notesInput)
  await user.type(notesInput, 'Nova observação')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(updatedBody).not.toBeNull())
  expect(updatedBody).toMatchObject({ row_version: 2, notes: 'Nova observação' })
  expect(await screen.findByText('Nova observação')).toBeInTheDocument()
})

test('shows a reload action when saving notes hits a version conflict', async () => {
  const user = userEvent.setup()
  const confirmed = draftAttendance({ status: 'CONFIRMED', notes: 'Original', row_version: 2 })
  server.use(
    attendanceHandler(confirmed),
    timelineHandler([]),
    http.patch('/api/v1/attendances/a1', () =>
      HttpResponse.json(
        { error: { code: 'CONFLICT', message: 'O registro foi alterado por outra operação.' } },
        { status: 409 },
      ),
    ),
  )
  renderPage(['attendances.read', 'attendances.update'])

  await screen.findByText('Original')
  await user.click(screen.getByRole('button', { name: 'Editar' }))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByText('O registro foi alterado por outra operação.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Recarregar atendimento' })).toBeInTheDocument()
})

test('does not show a notes edit button for a user without attendances.update', async () => {
  renderPage(
    ['attendances.read'],
    [attendanceHandler(draftAttendance({ status: 'CONFIRMED' })), timelineHandler([])],
  )

  await screen.findByText('Nenhuma observação registrada.')
  expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()
})

test('expands the timeline and paginates through history entries', async () => {
  const user = userEvent.setup()
  server.use(
    attendanceHandler(draftAttendance({ status: 'CONFIRMED', protocol_number: '2026/000001' })),
    http.get('/api/v1/attendances/a1/timeline', ({ request }) => {
      const url = new URL(request.url)
      const page = url.searchParams.get('page')
      const items =
        page === '2'
          ? [timelineEntry({ id: 't2', action: 'attendances.updated' })]
          : [timelineEntry({ id: 't1', action: 'attendances.confirmed' })]
      return HttpResponse.json({ items, total: 2, page: Number(page ?? 1), page_size: 1 })
    }),
  )
  renderPage(['attendances.read'])

  await screen.findByText('2026/000001')
  await user.click(screen.getByRole('button', { name: 'Ver histórico' }))

  expect(await screen.findByText('Atendimento confirmado')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Próxima página do histórico' }))

  expect(await screen.findByText('Atendimento editado')).toBeInTheDocument()
})

test('shows an empty-state message when the timeline has no entries', async () => {
  const user = userEvent.setup()
  renderPage(
    ['attendances.read'],
    [attendanceHandler(draftAttendance({ status: 'CONFIRMED' })), timelineHandler([])],
  )

  await user.click(await screen.findByRole('button', { name: 'Ver histórico' }))

  expect(await screen.findByText('Nenhum evento registrado.')).toBeInTheDocument()
})

test('shows the current clinic, veterinarian and patient on the DRAFT confirmation screen', async () => {
  renderPage(
    ['attendances.read', 'attendances.update'],
    [attendanceHandler(draftAttendance()), timelineHandler([]), ...headerDetailsHandlers()],
  )

  expect(await screen.findByText('Clínica Central')).toBeInTheDocument()
  expect(screen.getByText('Dra. Ana')).toBeInTheDocument()
  expect(screen.getByText('Bidu · Tutor: Maria Souza')).toBeInTheDocument()
  expect(screen.getByText('05 de jan. de 2026')).toBeInTheDocument()
})

test('hides the header edit button without attendances.update on a DRAFT attendance', async () => {
  renderPage(
    ['attendances.read'],
    [attendanceHandler(draftAttendance()), timelineHandler([]), ...headerDetailsHandlers()],
  )

  await screen.findByText('Clínica Central')
  expect(screen.queryByRole('button', { name: 'Editar dados' })).not.toBeInTheDocument()
})

test('never offers a header edit button on a non-DRAFT attendance', async () => {
  renderPage(
    ['attendances.read', 'attendances.update'],
    [
      attendanceHandler(draftAttendance({ status: 'CONFIRMED', protocol_number: '2026/000001' })),
      timelineHandler([]),
      ...headerDetailsHandlers(),
    ],
  )

  expect(await screen.findByText('Clínica Central')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Editar dados' })).not.toBeInTheDocument()
})

test('edits clinic, veterinarian, patient and service date of a DRAFT attendance', async () => {
  const user = userEvent.setup()
  let updatedBody: Record<string, unknown> | null = null
  let currentAttendance = draftAttendance()
  server.use(
    http.get('/api/v1/attendances/a1', () => HttpResponse.json(currentAttendance)),
    timelineHandler([]),
    ...headerDetailsHandlers(),
    http.patch('/api/v1/attendances/a1', async ({ request }) => {
      updatedBody = (await request.json()) as Record<string, unknown>
      currentAttendance = draftAttendance({
        clinic_id: 'c2',
        veterinarian_id: 'v1',
        patient_id: 'p2',
        service_date: '2026-02-10',
        notes: 'Trocado durante edição',
        row_version: 2,
      })
      return HttpResponse.json(currentAttendance)
    }),
  )
  renderPage(['attendances.read', 'attendances.update'])

  expect(await screen.findByText('Clínica Central')).toBeInTheDocument()
  await screen.findByText('Bidu · Tutor: Maria Souza')
  await user.click(screen.getByRole('button', { name: 'Editar dados' }))

  await user.selectOptions(screen.getByLabelText('Clínica solicitante'), 'Clínica Norte')
  await user.selectOptions(screen.getByLabelText('Veterinário responsável'), 'Dra. Ana')

  await user.click(screen.getByRole('button', { name: 'Trocar' }))
  await user.type(screen.getByLabelText('Paciente'), 'Thor')
  await user.click(await screen.findByRole('option', { name: /Thor/ }))

  const dateInput = screen.getByLabelText('Data do atendimento')
  fireEvent.change(dateInput, { target: { value: '2026-02-10' } })

  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(updatedBody).not.toBeNull())
  expect(updatedBody).toMatchObject({
    row_version: 1,
    clinic_id: 'c2',
    veterinarian_id: 'v1',
    patient_id: 'p2',
    service_date: '2026-02-10',
  })
  expect(await screen.findByText('Clínica Norte')).toBeInTheDocument()
  expect(screen.getByText('Thor · Tutor: Marcelo Andrade')).toBeInTheDocument()
})

test('shows a reload action when saving the header hits a version conflict', async () => {
  const user = userEvent.setup()
  server.use(
    attendanceHandler(draftAttendance()),
    timelineHandler([]),
    ...headerDetailsHandlers(),
    http.patch('/api/v1/attendances/a1', () =>
      HttpResponse.json(
        { error: { code: 'CONFLICT', message: 'O atendimento foi alterado por outra operação.' } },
        { status: 409 },
      ),
    ),
  )
  renderPage(['attendances.read', 'attendances.update'])

  await screen.findByText('Clínica Central')
  await screen.findByText('Bidu · Tutor: Maria Souza')
  await user.click(screen.getByRole('button', { name: 'Editar dados' }))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(
    await screen.findByText('O atendimento foi alterado por outra operação.'),
  ).toBeInTheDocument()
  expect(
    screen.getAllByRole('button', { name: 'Recarregar atendimento' }).length,
  ).toBeGreaterThan(0)
})
