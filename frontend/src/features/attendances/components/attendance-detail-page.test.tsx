import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { AttendanceDetailPage } from './attendance-detail-page'
import { pickOption } from '../../../test/dropdown'

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
    clinic_id: 'c1',
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
  components: [],
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
    ['attendances.read', 'pricing.read'],
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
  expect(document.querySelector('.attendance-readonly-detail__grand:last-child')).toHaveTextContent(
    'R$ 100,00',
  )
  expect(screen.queryByRole('button', { name: 'Confirmar atendimento' })).not.toBeInTheDocument()
  restart(view)

  // Sem pricing.read nenhum valor aparece na tela.
  view = renderPage(
    ['attendances.read'],
    [attendanceHandler(draftAttendance({ status: 'CONFIRMED', items: [confirmedItem] })), timelineHandler([])],
  )
  expect(await screen.findByText('Hemograma')).toBeInTheDocument()
  expect(screen.queryByText(/R\$/)).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Valor' })).not.toBeInTheDocument()
  restart(view)

  // Sem attendances.update não há edição de observações.
  view = renderPage(
    ['attendances.read'],
    [attendanceHandler(draftAttendance({ status: 'CONFIRMED' })), timelineHandler([])],
  )
  await screen.findByText('Nenhuma observação registrada.')
  expect(screen.queryByRole('button', { name: /^Editar/ })).not.toBeInTheDocument()
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

test('a DRAFT opens in Novo Protocolo already filled and can be discarded with a reason', async () => {
  const user = userEvent.setup()
  let createdDraft = false
  let cancelledBody: Record<string, unknown> | null = null
  const draft = draftAttendance({
    collection_method: 'UBER',
    service_level: 'PLANTAO_NORMAL',
    notes: 'Coleta urgente',
  })
  renderPage(
    ['attendances.read', 'attendances.create', 'attendances.update', 'attendances.cancel'],
    [
      attendanceHandler(draft),
      timelineHandler([]),
      ...headerDetailsHandlers(),
      http.get('/api/v1/species', () =>
        HttpResponse.json({
          items: [{ id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' }],
        }),
      ),
      http.get('/api/v1/exams', () =>
        HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
      ),
      http.get('/api/v1/exam-categories/active', () => HttpResponse.json({ items: [] })),
      http.post('/api/v1/attendances/drafts', () => {
        createdDraft = true
        return HttpResponse.json(draft, { status: 201 })
      }),
      http.post('/api/v1/attendances/a1/cancel', async ({ request }) => {
        cancelledBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ ...draft, status: 'CANCELLED', cancel_reason: 'Pedido do tutor' })
      }),
    ],
  )

  expect(await screen.findByText('Rascunho de protocolo')).toBeInTheDocument()
  expect(await screen.findByDisplayValue('Coleta urgente')).toBeInTheDocument()
  expect(await screen.findByText('Bidu')).toBeInTheDocument()
  // Retomar não cria outro rascunho.
  expect(createdDraft).toBe(false)

  await user.click(screen.getByRole('button', { name: 'Descartar rascunho' }))
  expect(screen.getByRole('button', { name: 'Confirmar cancelamento' })).toBeDisabled()
  await user.type(await screen.findByLabelText('Motivo do cancelamento'), 'Pedido do tutor')
  await user.click(screen.getByRole('button', { name: 'Confirmar cancelamento' }))
  await waitFor(() => expect(cancelledBody).not.toBeNull())
  expect(cancelledBody).toMatchObject({ reason: 'Pedido do tutor' })
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
  await user.click(screen.getByRole('button', { name: 'Editar observações' }))
  const notesInput = screen.getByRole('textbox', { name: 'Observações' })
  await user.clear(notesInput)
  await user.type(notesInput, 'Nova observação')
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Texto corrigido')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(updatedBody).not.toBeNull())
  expect(updatedBody).toMatchObject({
    row_version: 2,
    notes: 'Nova observação',
    reason: 'Texto corrigido',
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
  await user.click(screen.getByRole('button', { name: 'Editar observações' }))
  await user.type(screen.getByRole('textbox', { name: 'Observações' }), ' (revisada)')
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Correção')
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

test('every block of a confirmed attendance can be corrected with a reason', async () => {
  const user = userEvent.setup()
  let patchBody: Record<string, unknown> | null = null
  const confirmed = draftAttendance({
    status: 'CONFIRMED',
    protocol_number: 'P000001/26',
    service_level: 'NORMAL',
    collection_method: 'INTERNAL',
    row_version: 2,
  })
  renderPage(
    ['attendances.read', 'attendances.update'],
    [
      attendanceHandler(confirmed),
      timelineHandler([]),
      ...headerDetailsHandlers(),
      http.patch('/api/v1/attendances/a1', async ({ request }) => {
        patchBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ ...confirmed, service_level: 'PLANTAO_NORMAL', row_version: 3 })
      }),
    ],
  )

  await screen.findByText('P000001/26')
  for (const block of ['solicitante', 'paciente', 'atendimento', 'exames', 'observações']) {
    expect(screen.getByRole('button', { name: `Editar ${block}` })).toBeInTheDocument()
  }

  await user.click(screen.getByRole('button', { name: 'Editar atendimento' }))
  await pickOption(user, 'Tipo de atendimento', 'Plantão Normal')
  // Sem motivo não salva.
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Era plantão')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(patchBody).not.toBeNull())
  expect(patchBody).toEqual({
    row_version: 2,
    service_level: 'PLANTAO_NORMAL',
    reason: 'Era plantão',
  })
})

test('editing the exams of a confirmed attendance sends the whole desired set with a reason', async () => {
  const user = userEvent.setup()
  let putBody: Record<string, unknown> | null = null
  const confirmed = draftAttendance({
    status: 'CONFIRMED',
    protocol_number: 'P000001/26',
    row_version: 2,
    items: [
      {
        id: 'i1',
        exam_id: 'e1',
        exam_code: 'HEMO',
        exam_name: 'Hemograma',
        price_base: '100.00',
        components: [],
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
  })
  const ureia = { ...hemograma(), id: 'e2', code: 'UREIA', name: 'Ureia', species_ids: ['s1'] }
  renderPage(
    ['attendances.read', 'attendances.update', 'pricing.read'],
    [
      attendanceHandler(confirmed),
      timelineHandler([]),
      ...headerDetailsHandlers(),
      http.get('/api/v1/exams', () =>
        HttpResponse.json({
          items: [{ ...hemograma(), species_ids: ['s1'] }, ureia],
          total: 2,
          page: 1,
          page_size: 100,
        }),
      ),
      http.get('/api/v1/exam-categories/active', () =>
        HttpResponse.json({
          items: [{ id: 'cat1', name: 'Hematologia', status: 'ACTIVE', row_version: 1 }],
        }),
      ),
      http.put('/api/v1/attendances/a1/items', async ({ request }) => {
        putBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ ...confirmed, row_version: 3 })
      }),
    ],
  )

  await screen.findByText('P000001/26')
  await user.click(screen.getByRole('button', { name: 'Editar exames' }))
  // O exame já lançado vem marcado; marcar outro o inclui.
  const hemogramaBox = await screen.findByRole('checkbox', { name: /Hemograma/ })
  expect(hemogramaBox).toBeChecked()
  await user.click(await screen.findByRole('checkbox', { name: /Ureia/ }))
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Solicitante pediu mais um')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(putBody).not.toBeNull())
  expect(putBody).toEqual({
    row_version: 2,
    reason: 'Solicitante pediu mais um',
    items: [
      { item_id: 'i1', quantity: 1 },
      { exam_id: 'e2', quantity: 1 },
    ],
  })
})

test('the exam grid shows the snapshot price of a launched exam, not the catalog price', async () => {
  const user = userEvent.setup()
  const confirmed = draftAttendance({
    status: 'CONFIRMED',
    protocol_number: 'P000001/26',
    row_version: 2,
    items: [{ ...confirmedItem, price_base: '90.00', total_amount: '90.00' }],
  })
  renderPage(
    ['attendances.read', 'attendances.update', 'pricing.read'],
    [
      attendanceHandler(confirmed),
      timelineHandler([]),
      ...headerDetailsHandlers(),
      http.get('/api/v1/exams', () =>
        HttpResponse.json({
          items: [{ ...hemograma(), species_ids: ['s1'], price_base: '100.00' }],
          total: 1,
          page: 1,
          page_size: 100,
        }),
      ),
      http.get('/api/v1/exam-categories/active', () =>
        HttpResponse.json({
          items: [{ id: 'cat1', name: 'Hematologia', status: 'ACTIVE', row_version: 1 }],
        }),
      ),
    ],
  )

  await screen.findByText('P000001/26')
  await user.click(screen.getByRole('button', { name: 'Editar exames' }))
  const row = await screen.findByRole('checkbox', { name: /Hemograma/ })
  expect(row).toBeChecked()
  expect(row.closest('li, div')?.textContent ?? '').toContain('90,00')
  expect(screen.queryByText(/100,00/)).not.toBeInTheDocument()
})

test('the patient record can be corrected from the attendance only with patients.manage', async () => {
  const user = userEvent.setup()
  let patchBody: Record<string, unknown> | null = null
  const confirmed = draftAttendance({ status: 'CONFIRMED', protocol_number: 'P000001/26' })
  const handlers = [
    attendanceHandler(confirmed),
    timelineHandler([]),
    ...headerDetailsHandlers(),
    http.get('/api/v1/species', () =>
      HttpResponse.json({
        items: [{ id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' }],
      }),
    ),
    http.patch('/api/v1/patients/p1', async ({ request }) => {
      patchBody = (await request.json()) as Record<string, unknown>
      return HttpResponse.json({ ...patient(), name: 'Bidu Júnior', row_version: 2 })
    }),
  ]

  const view = renderPage(['attendances.read', 'attendances.update'], handlers)
  await screen.findByText('P000001/26')
  expect(screen.queryByRole('button', { name: 'Corrigir cadastro' })).not.toBeInTheDocument()
  restart(view)

  renderPage(['attendances.read', 'attendances.update', 'patients.manage'], handlers)
  await user.click(await screen.findByRole('button', { name: 'Corrigir cadastro' }))
  const dialog = await screen.findByRole('dialog')
  const name = await within(dialog).findByLabelText('Nome do paciente')
  await user.clear(name)
  await user.type(name, 'Bidu Júnior')
  await user.click(within(dialog).getByRole('button', { name: /Salvar/ }))

  await waitFor(() => expect(patchBody).not.toBeNull())
  expect(patchBody).toMatchObject({ name: 'Bidu Júnior', expected_row_version: 1 })
})
