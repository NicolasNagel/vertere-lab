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
    on_call_fee: '0.00',
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
  return {
    ...veterinarian(),
    id: 'v2',
    name: 'Dr. Bruno',
    is_autonomous: false,
  }
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
  return {
    ...patient(),
    id: 'p2',
    name: 'Thor',
    owner_name: 'Marcelo Andrade',
  }
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
      HttpResponse.json({
        items: [clinic(), clinicNorte()],
        total: 2,
        page: 1,
        page_size: 100,
      }),
    ),
    http.get('/api/v1/veterinarians', ({ request }) => {
      const url = new URL(request.url)
      const availableForClinicId = url.searchParams.get('available_for_clinic_id')
      const items =
        !availableForClinicId || availableForClinicId === 'c1'
          ? [veterinarian(), veterinarianBruno()]
          : [veterinarian()]
      return HttpResponse.json({
        items,
        total: items.length,
        page: 1,
        page_size: 100,
      })
    }),
    http.get('/api/v1/patients', ({ request }) => {
      const url = new URL(request.url)
      const search = url.searchParams.get('search')
      const items = search?.toLowerCase().includes('thor') ? [patientThor()] : []
      return HttpResponse.json({
        items,
        total: items.length,
        page: 1,
        page_size: 10,
      })
    }),
  ]
}

function examSearchHandler(matches: Record<string, unknown>[]) {
  return http.get('/api/v1/exams', ({ request }) => {
    const url = new URL(request.url)
    const search = url.searchParams.get('search')
    const items = search ? matches : []
    return HttpResponse.json({
      items,
      total: items.length,
      page: 1,
      page_size: 10,
    })
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
      on_call_fee: '0.00',
      grand_total: '200.00',
    }),
  )
}

function renderPage(permissions: string[], handlers: ReturnType<typeof http.get>[] = []) {
  server.use(...handlers, meHandler(permissions))
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
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

// Cada cenário reinicia a árvore e os handlers do MSW entre as fases para que
// uma fase não herde resposta da anterior.
function restart(view: ReturnType<typeof renderPage>) {
  view.unmount()
  server.resetHandlers()
}

const confirmedItem = {
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
}

test('gates the page by permission, handles not-found and renders non-draft attendances read-only', async () => {
  // Sem attendances.read.
  let view = renderPage([], [attendanceHandler(draftAttendance())])
  expect(
    await screen.findByText('Você não tem permissão para visualizar atendimentos.'),
  ).toBeInTheDocument()
  restart(view)

  // Atendimento inexistente.
  server.use(
    http.get('/api/v1/attendances/a1', () =>
      HttpResponse.json(
        { error: { code: 'NOT_FOUND', message: 'Não encontrado.' } },
        { status: 404 },
      ),
    ),
  )
  view = renderPage(['attendances.read'])
  expect(await screen.findByText('Atendimento não encontrado.')).toBeInTheDocument()
  restart(view)

  // Confirmado: visão somente leitura com protocolo, exame, categoria e total.
  view = renderPage(
    ['attendances.read'],
    [
      attendanceHandler(
        draftAttendance({
          status: 'CONFIRMED',
          protocol_number: 'P000001/26',
          items: [confirmedItem],
          subtotal: '100.00',
          grand_total: '100.00',
        }),
      ),
      http.get('/api/v1/exams/e1', () => HttpResponse.json(hemograma())),
      http.get('/api/v1/exam-categories/cat1', () =>
        HttpResponse.json({
          id: 'cat1',
          name: 'Hematológico',
          status: 'ACTIVE',
          row_version: 1,
        }),
      ),
      timelineHandler([]),
    ],
  )
  expect(await screen.findByText('P000001/26')).toBeInTheDocument()
  expect(screen.getAllByText('Hemograma').length).toBeGreaterThan(0)
  expect(await screen.findByText('Hematológico')).toBeInTheDocument()
  expect(document.querySelector('.attendance-readonly-detail__total-value')).toHaveTextContent(
    'R$ 100,00',
  )
  expect(screen.queryByRole('button', { name: 'Confirmar atendimento' })).not.toBeInTheDocument()
  restart(view)

  // Sem attendances.update não há edição de observações.
  view = renderPage(
    ['attendances.read'],
    [attendanceHandler(draftAttendance({ status: 'CONFIRMED' })), timelineHandler([])],
  )
  await screen.findByText('Nenhuma observação registrada.')
  expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()
  restart(view)

  // Cancelado não oferece cancelar de novo.
  view = renderPage(
    ['attendances.read', 'attendances.cancel'],
    [
      attendanceHandler(draftAttendance({ status: 'CANCELLED', cancel_reason: 'x' })),
      timelineHandler([]),
    ],
  )
  await screen.findByText('Cancelado')
  expect(screen.queryByRole('button', { name: 'Cancelar atendimento' })).not.toBeInTheDocument()
})

test('a DRAFT adds an exam, shows the backend-computed total and confirms with an idempotency key', async () => {
  const user = userEvent.setup()
  let confirmedBody: Record<string, unknown> | null = null
  let currentAttendance = draftAttendance()
  const confirmedAttendance = draftAttendance({
    status: 'CONFIRMED',
    protocol_number: 'P000001/26',
    items: [{ ...confirmedItem, quantity: 2, total_amount: '200.00' }],
    subtotal: '200.00',
    grand_total: '200.00',
  })
  server.use(
    http.get('/api/v1/attendances/a1', () => HttpResponse.json(currentAttendance)),
    examSearchHandler([hemograma()]),
    previewHandler([
      {
        ...confirmedItem,
        id: 'preview-1',
        quantity: 2,
        total_amount: '200.00',
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

  // Sem exame não há o que confirmar.
  expect(await screen.findByRole('button', { name: 'Confirmar atendimento' })).toBeDisabled()

  await user.type(await screen.findByLabelText('Adicionar exame'), 'Hemo')
  await user.click(await screen.findByRole('option', { name: /Hemograma/ }))

  // Sem attendances.override_price o desconto fica oculto.
  fireEvent.change(await screen.findByLabelText('Quantidade'), {
    target: { value: '2' },
  })
  expect(screen.queryByLabelText('Desconto (R$)')).not.toBeInTheDocument()

  await waitFor(
    () =>
      expect(document.querySelector('.attendance-summary-panel__total-value')).toHaveTextContent(
        'R$ 200,00',
      ),
    { timeout: 3000 },
  )

  await user.click(screen.getByRole('button', { name: 'Confirmar atendimento' }))

  await waitFor(() => expect(confirmedBody).not.toBeNull())
  expect(confirmedBody).toMatchObject({
    items: [{ exam_id: 'e1', quantity: 2 }],
  })
  expect(await screen.findByText('P000001/26')).toBeInTheDocument()
})

test('cancelling a DRAFT requires a permission and a non-empty reason', async () => {
  const user = userEvent.setup()
  // Sem attendances.cancel o botão não aparece.
  let view = renderPage(
    ['attendances.read', 'attendances.update'],
    [attendanceHandler(draftAttendance()), timelineHandler([])],
  )
  await screen.findByLabelText('Adicionar exame')
  expect(screen.queryByRole('button', { name: 'Cancelar atendimento' })).not.toBeInTheDocument()
  restart(view)

  let cancelledBody: Record<string, unknown> | null = null
  let currentAttendance = draftAttendance()
  const cancelledAttendance = draftAttendance({
    status: 'CANCELLED',
    cancel_reason: 'Pedido do tutor',
  })
  view = renderPage(
    ['attendances.read', 'attendances.update', 'attendances.cancel'],
    [
      http.get('/api/v1/attendances/a1', () => HttpResponse.json(currentAttendance)),
      timelineHandler([]),
      http.post('/api/v1/attendances/a1/cancel', async ({ request }) => {
        cancelledBody = (await request.json()) as Record<string, unknown>
        currentAttendance = cancelledAttendance
        return HttpResponse.json(cancelledAttendance)
      }),
    ],
  )

  await user.click(await screen.findByRole('button', { name: 'Cancelar atendimento' }))
  expect(screen.getByRole('button', { name: 'Confirmar cancelamento' })).toBeDisabled()
  await user.type(await screen.findByLabelText('Motivo do cancelamento'), 'Pedido do tutor')
  await user.click(screen.getByRole('button', { name: 'Confirmar cancelamento' }))

  await waitFor(() => expect(cancelledBody).not.toBeNull())
  expect(cancelledBody).toMatchObject({ reason: 'Pedido do tutor' })
  expect(await screen.findByText('Motivo do cancelamento: Pedido do tutor')).toBeInTheDocument()
})

test('edits the notes of a CONFIRMED attendance and offers a reload on a version conflict', async () => {
  const user = userEvent.setup()
  let updatedBody: Record<string, unknown> | null = null
  let currentAttendance = draftAttendance({
    status: 'CONFIRMED',
    protocol_number: 'P000001/26',
    notes: 'Observação original',
    row_version: 2,
  })
  let view = renderPage(
    ['attendances.read', 'attendances.update'],
    [
      http.get('/api/v1/attendances/a1', () => HttpResponse.json(currentAttendance)),
      timelineHandler([]),
      http.patch('/api/v1/attendances/a1', async ({ request }) => {
        updatedBody = (await request.json()) as Record<string, unknown>
        currentAttendance = draftAttendance({
          status: 'CONFIRMED',
          protocol_number: 'P000001/26',
          notes: 'Nova observação',
          row_version: 3,
        })
        return HttpResponse.json(currentAttendance)
      }),
    ],
  )

  expect(await screen.findByText('Observação original')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Editar' }))
  const notesInput = screen.getByLabelText('Observações')
  await user.clear(notesInput)
  await user.type(notesInput, 'Nova observação')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(updatedBody).not.toBeNull())
  expect(updatedBody).toMatchObject({
    row_version: 2,
    notes: 'Nova observação',
  })
  expect(await screen.findByText('Nova observação')).toBeInTheDocument()
  restart(view)

  // Conflito de versão oferece recarregar.
  view = renderPage(
    ['attendances.read', 'attendances.update'],
    [
      attendanceHandler(
        draftAttendance({
          status: 'CONFIRMED',
          notes: 'Original',
          row_version: 2,
        }),
      ),
      timelineHandler([]),
      http.patch('/api/v1/attendances/a1', () =>
        HttpResponse.json(
          {
            error: {
              code: 'CONFLICT',
              message: 'O registro foi alterado por outra operação.',
            },
          },
          { status: 409 },
        ),
      ),
    ],
  )
  await screen.findByText('Original')
  await user.click(screen.getByRole('button', { name: 'Editar' }))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  expect(await screen.findByText('O registro foi alterado por outra operação.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Recarregar atendimento' })).toBeInTheDocument()
})

test('the timeline expands, paginates and shows an empty state', async () => {
  const user = userEvent.setup()
  let view = renderPage(
    ['attendances.read'],
    [
      attendanceHandler(draftAttendance({ status: 'CONFIRMED', protocol_number: 'P000001/26' })),
      http.get('/api/v1/attendances/a1/timeline', ({ request }) => {
        const page = new URL(request.url).searchParams.get('page')
        const items =
          page === '2'
            ? [timelineEntry({ id: 't2', action: 'attendances.updated' })]
            : [timelineEntry({ id: 't1', action: 'attendances.confirmed' })]
        return HttpResponse.json({
          items,
          total: 2,
          page: Number(page ?? 1),
          page_size: 1,
        })
      }),
    ],
  )

  await screen.findByText('P000001/26')
  await user.click(screen.getByRole('button', { name: 'Ver histórico' }))
  expect(await screen.findByText('Atendimento confirmado')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Próxima página do histórico' }))
  expect(await screen.findByText('Atendimento editado')).toBeInTheDocument()
  restart(view)

  view = renderPage(
    ['attendances.read'],
    [attendanceHandler(draftAttendance({ status: 'CONFIRMED' })), timelineHandler([])],
  )
  await user.click(await screen.findByRole('button', { name: 'Ver histórico' }))
  expect(await screen.findByText('Nenhum evento registrado.')).toBeInTheDocument()
})

test('the header of a DRAFT shows clinic, veterinarian and patient and can be edited only with permission', async () => {
  const user = userEvent.setup()
  const baseHandlers = [timelineHandler([]), ...headerDetailsHandlers()]

  // Leitura: mostra os dados e, sem attendances.update, não oferece edição.
  let view = renderPage(
    ['attendances.read'],
    [attendanceHandler(draftAttendance()), ...baseHandlers],
  )
  expect(await screen.findByText('Clínica Central')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Editar dados' })).not.toBeInTheDocument()
  restart(view)

  // Fora de DRAFT nunca há edição de cabeçalho.
  view = renderPage(
    ['attendances.read', 'attendances.update'],
    [
      attendanceHandler(draftAttendance({ status: 'CONFIRMED', protocol_number: 'P000001/26' })),
      ...baseHandlers,
    ],
  )
  expect(await screen.findByText('Clínica Central')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Editar dados' })).not.toBeInTheDocument()
  restart(view)

  // Com permissão: exibe, edita e salva.
  let updatedBody: Record<string, unknown> | null = null
  let currentAttendance = draftAttendance()
  view = renderPage(
    ['attendances.read', 'attendances.update'],
    [
      http.get('/api/v1/attendances/a1', () => HttpResponse.json(currentAttendance)),
      ...baseHandlers,
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
    ],
  )
  expect(await screen.findByText('Clínica Central')).toBeInTheDocument()
  expect(screen.getByText('Dra. Ana')).toBeInTheDocument()
  expect(await screen.findByText('Bidu · Tutor: Maria Souza')).toBeInTheDocument()
  expect(screen.getByText('05 de jan. de 2026')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Editar dados' }))

  await user.selectOptions(screen.getByLabelText('Clínica solicitante'), 'Clínica Norte')
  await user.selectOptions(screen.getByLabelText('Veterinário responsável'), 'Dra. Ana')
  await user.click(screen.getByRole('button', { name: 'Trocar' }))
  await user.type(screen.getByLabelText('Paciente'), 'Thor')
  await user.click(await screen.findByRole('option', { name: /Thor/ }))
  fireEvent.change(screen.getByLabelText('Data do atendimento'), {
    target: { value: '2026-02-10' },
  })
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
  restart(view)

  // Conflito de versão no cabeçalho oferece recarregar.
  view = renderPage(
    ['attendances.read', 'attendances.update'],
    [
      attendanceHandler(draftAttendance()),
      ...baseHandlers,
      http.patch('/api/v1/attendances/a1', () =>
        HttpResponse.json(
          {
            error: {
              code: 'CONFLICT',
              message: 'O atendimento foi alterado por outra operação.',
            },
          },
          { status: 409 },
        ),
      ),
    ],
  )
  await screen.findByText('Clínica Central')
  await screen.findByText('Bidu · Tutor: Maria Souza')
  await user.click(screen.getByRole('button', { name: 'Editar dados' }))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  expect(
    await screen.findByText('O atendimento foi alterado por outra operação.'),
  ).toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: 'Recarregar atendimento' }).length).toBeGreaterThan(
    0,
  )
})
