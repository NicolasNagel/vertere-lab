import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test, vi } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { AttendanceDraftPage } from './attendance-draft-page'

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

function veterinariansHandler() {
  // O filtro "disponível para esta clínica" é resolvido no servidor
  // (`available_for_clinic_id`) — a listagem nunca carregou `clinics` por
  // item, então este mock simula a mesma regra que o backend aplica:
  // autônomo sempre aparece; vinculado só aparece para a clínica certa.
  const autonomous = {
    id: 'v1',
    name: 'Dra. Ana (autônoma)',
    crmv: 'CRMV-SC 0001',
    phone: null,
    email: null,
    is_autonomous: true,
    status: 'ACTIVE',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    row_version: 1,
  }
  const linkedToC1 = {
    id: 'v2',
    name: 'Dr. Bruno (vinculado c1)',
    crmv: 'CRMV-SC 0002',
    phone: null,
    email: null,
    is_autonomous: false,
    status: 'ACTIVE',
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    row_version: 1,
  }
  return http.get('/api/v1/veterinarians', ({ request }) => {
    const url = new URL(request.url)
    const availableForClinicId = url.searchParams.get('available_for_clinic_id')
    const items =
      !availableForClinicId || availableForClinicId === 'c1'
        ? [autonomous, linkedToC1]
        : [autonomous]
    return HttpResponse.json({ items, total: items.length, page: 1, page_size: 100 })
  })
}

function patientSearchHandler(matches: Record<string, unknown>[]) {
  return http.get('/api/v1/patients', ({ request }) => {
    const url = new URL(request.url)
    const search = url.searchParams.get('search')
    const items = search ? matches : []
    return HttpResponse.json({ items, total: items.length, page: 1, page_size: 10 })
  })
}

function bidu() {
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

/** Uma vez que o rascunho é criado automaticamente, `AttendanceConfirmationForm`
 * assume a tela e busca clínica/veterinário/paciente por ID (via
 * `AttendanceHeaderDetails`) — sem esses handlers a chamada não mockada
 * quebraria o teste (`onUnhandledRequest: 'error'`). */
function confirmationFormDetailHandlers() {
  return [
    http.get('/api/v1/clinics/c1', () =>
      HttpResponse.json({
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
      }),
    ),
    http.get('/api/v1/veterinarians/v2', () =>
      HttpResponse.json({
        id: 'v2',
        name: 'Dr. Bruno (vinculado c1)',
        crmv: 'CRMV-SC 0002',
        phone: null,
        email: null,
        is_autonomous: false,
        status: 'ACTIVE',
        notes: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        row_version: 1,
        clinics: [],
      }),
    ),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(bidu())),
  ]
}

function draftCreatedResponse(body: Record<string, unknown>) {
  return {
    id: 'a1',
    clinic_id: body.clinic_id,
    veterinarian_id: body.veterinarian_id,
    patient_id: body.patient_id,
    service_date: body.service_date,
    collection_method: body.collection_method,
    service_level: body.service_level,
    notes: body.notes,
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
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    row_version: 1,
  }
}

function examsCatalogHandlers(exams: Record<string, unknown>[] = []) {
  return [
    http.get('/api/v1/exams', () =>
      HttpResponse.json({ items: exams, total: exams.length, page: 1, page_size: 100 }),
    ),
    http.get('/api/v1/exam-categories/active', () =>
      HttpResponse.json({
        items: [{ id: 'cat1', name: 'Hematologia', status: 'ACTIVE', row_version: 1 }],
      }),
    ),
  ]
}

const hemogramaApi = {
  id: 'e1',
  code: 'HEMO',
  name: 'Hemograma',
  category_id: 'cat1',
  description: null,
  species_ids: ['s1'],
  component_exam_ids: [],
  is_panel: false,
  status: 'ACTIVE',
  row_version: 1,
  price_base: '100.00',
  updated_at: '2026-01-01T00:00:00Z',
}

function renderPage(permissions: string[], handlers: ReturnType<typeof http.get>[] = []) {
  // Handlers passados aqui vêm ANTES dos defaults — MSW resolve pelo
  // primeiro handler compatível na lista, então isso é o que permite um
  // teste sobrescrever, por exemplo, a busca de pacientes.
  server.use(
    ...handlers,
    meHandler(permissions),
    ...examsCatalogHandlers(),
    clinicsHandler(),
    veterinariansHandler(),
    patientSearchHandler([]),
  )
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(
    [
      { path: '/operacao/novo', element: <AttendanceDraftPage /> },
      { path: '/operacao', element: <div>Lista de atendimentos</div> },
    ],
    { initialEntries: ['/operacao/novo'] },
  )
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{withRouter(router)}</AuthProvider>
    </QueryClientProvider>,
  )

  function withRouter(r: typeof router): ReactNode {
    return <RouterProvider router={r} />
  }
}

function speciesHandler() {
  return http.get('/api/v1/species', () =>
    HttpResponse.json({
      items: [{ id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' }],
    }),
  )
}

function createPatientHandler() {
  return http.post('/api/v1/patients', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    return HttpResponse.json(
      {
        id: 'p1',
        name: body.name,
        species_id: body.species_id,
        sex: body.sex,
        breed: null,
        age_description: null,
        owner_name: body.owner_name,
        owner_phone: null,
        owner_document: null,
        status: 'ACTIVE',
        notes: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        row_version: 1,
      },
      { status: 201 },
    )
  })
}

type User = ReturnType<typeof userEvent.setup>

/** Abre o menu suspenso do campo e escolhe a opção (o `<select>` nativo virou dropdown próprio). */
async function chooseOption(user: User, field: string, option: string) {
  const trigger = await screen.findByRole('button', { name: new RegExp(`^${field}`) })
  await waitFor(() => expect(trigger).toBeEnabled())
  await user.click(trigger)
  await user.click(await screen.findByRole('option', { name: option }))
}

async function listOptions(user: User, field: string): Promise<string[]> {
  await user.click(await screen.findByRole('button', { name: new RegExp(`^${field}`) }))
  const labels = screen.getAllByRole('option').map((option) => option.textContent ?? '')
  await user.keyboard('{Escape}')
  return labels
}

async function fillAndSavePatientForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Nome do paciente'), 'Bidu')
  await chooseOption(user, 'Espécie', 'Canino')
  await user.type(screen.getByLabelText('Tutor / Proprietário'), 'Maria Souza')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
}

test('requires attendances.create and filters the veterinarian list by the selected clinic', async () => {
  const user = userEvent.setup()
  const denied = renderPage([])
  expect(
    await screen.findByText('Você não tem permissão para criar atendimentos.'),
  ).toBeInTheDocument()
  denied.unmount()
  server.resetHandlers()

  renderPage(['attendances.create'])
  await chooseOption(user, 'Clínica solicitante', 'Clínica Central')

  const optionLabels = await listOptions(user, 'Veterinário responsável')
  expect(optionLabels).toContain('Dra. Ana (autônoma)')
  expect(optionLabels).toContain('Dr. Bruno (vinculado c1)')

  await chooseOption(user, 'Clínica solicitante', 'Clínica Norte')
  const optionLabelsAfter = await listOptions(user, 'Veterinário responsável')
  expect(optionLabelsAfter).toContain('Dra. Ana (autônoma)')
  expect(optionLabelsAfter).not.toContain('Dr. Bruno (vinculado c1)')
})

test('does not list the exam catalog until clinic, veterinarian and patient are chosen', async () => {
  const user = userEvent.setup()
  renderPage(['attendances.create'], examsCatalogHandlers([]))

  expect(
    await screen.findByText('Para marcar exames, falta informar: clínica, veterinário, paciente.'),
  ).toBeInTheDocument()
  expect(screen.queryByLabelText('Filtrar exames')).not.toBeInTheDocument()

  await chooseOption(user, 'Clínica solicitante', 'Clínica Central')
  expect(
    await screen.findByText('Para marcar exames, falta informar: veterinário, paciente.'),
  ).toBeInTheDocument()
})

test('auto-creates the draft once clinic, veterinarian and patient are set, then confirms and returns to the list', async () => {
  const user = userEvent.setup()
  const onDraftCreated = vi.fn()
  server.use(
    ...confirmationFormDetailHandlers(),
    speciesHandler(),
    createPatientHandler(),
    http.post('/api/v1/attendances/drafts', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      onDraftCreated(body)
      return HttpResponse.json(draftCreatedResponse(body), { status: 201 })
    }),
    http.post('/api/v1/attendances/a1/preview', async () =>
      HttpResponse.json({
        attendance_id: 'a1',
        clinic_id: 'c1',
        veterinarian_id: 'v2',
        patient_id: 'p1',
        service_date: '2026-01-01',
        items: [
          {
            id: 'preview-1',
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
        discount_total: '0.00',
        surcharge_total: '0.00',
        on_call_fee: '0.00',
        grand_total: '100.00',
      }),
    ),
    http.post('/api/v1/attendances/a1/confirm', async () =>
      HttpResponse.json(
        draftCreatedResponse({
          clinic_id: 'c1',
          veterinarian_id: 'v2',
          patient_id: 'p1',
          service_date: null,
          collection_method: 'INTERNAL',
          service_level: 'NORMAL',
          notes: null,
        }),
      ),
    ),
  )
  renderPage(['attendances.create', 'attendances.update'], examsCatalogHandlers([hemogramaApi]))

  await chooseOption(user, 'Clínica solicitante', 'Clínica Central')
  await chooseOption(user, 'Veterinário responsável', 'Dr. Bruno (vinculado c1)')
  expect(onDraftCreated).not.toHaveBeenCalled() // ainda falta o paciente

  await fillAndSavePatientForm(user)

  await waitFor(() => expect(onDraftCreated).toHaveBeenCalledTimes(1))
  expect(onDraftCreated).toHaveBeenCalledWith(
    expect.objectContaining({
      clinic_id: 'c1',
      veterinarian_id: 'v2',
      patient_id: 'p1',
      collection_method: 'INTERNAL',
      service_level: 'NORMAL',
    }),
  )
  // Os cards de Exames/Valor já estavam visíveis (layout estático) e ficam
  // ativos assim que o rascunho existe.
  const hemograma = await screen.findByRole('checkbox', { name: /Hemograma/ })
  await waitFor(() => expect(hemograma).toBeEnabled())
  await user.click(hemograma)
  await user.click(await screen.findByRole('button', { name: 'Abrir protocolo' }))

  expect(await screen.findByText('Lista de atendimentos')).toBeInTheDocument()
})

test('finding an existing patient from the history keeps the already-filled clinic and veterinarian', async () => {
  const user = userEvent.setup()
  const onDraftCreated = vi.fn()
  server.use(
    ...confirmationFormDetailHandlers(),
    http.post('/api/v1/attendances/drafts', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      onDraftCreated(body)
      return HttpResponse.json(draftCreatedResponse(body), { status: 201 })
    }),
  )
  renderPage(['attendances.create'], [patientSearchHandler([bidu()])])

  await chooseOption(user, 'Clínica solicitante', 'Clínica Central')
  await chooseOption(user, 'Veterinário responsável', 'Dr. Bruno (vinculado c1)')

  await user.click(screen.getByRole('button', { name: '+ buscar do histórico' }))
  await user.type(screen.getByRole('textbox', { name: 'Paciente' }), 'Bidu')
  await user.click(await screen.findByRole('option', { name: /Bidu/ }))

  await waitFor(() => expect(onDraftCreated).toHaveBeenCalledTimes(1))
  expect(onDraftCreated).toHaveBeenCalledWith(
    expect.objectContaining({ clinic_id: 'c1', veterinarian_id: 'v2', patient_id: 'p1' }),
  )
})
