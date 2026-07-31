import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
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

function renderPage(permissions: string[], handlers: ReturnType<typeof http.get>[] = []) {
  // Handlers passados aqui vêm ANTES dos defaults — MSW resolve pelo
  // primeiro handler compatível na lista, então isso é o que permite um
  // teste sobrescrever, por exemplo, a busca de pacientes.
  server.use(
    ...handlers,
    meHandler(permissions),
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

test('shows a permission-denied message for a user without attendances.create', async () => {
  renderPage([])

  expect(
    await screen.findByText('Você não tem permissão para criar atendimentos.'),
  ).toBeInTheDocument()
})

test('filters the veterinarian list by the selected clinic', async () => {
  const user = userEvent.setup()
  renderPage(['attendances.create'])

  await screen.findByRole('option', { name: 'Clínica Central' })
  await user.selectOptions(screen.getByLabelText('Clínica solicitante'), 'Clínica Central')

  const vetSelect = screen.getByLabelText('Veterinário responsável') as HTMLSelectElement
  const optionLabels = Array.from(vetSelect.options).map((option) => option.text)
  expect(optionLabels).toContain('Dra. Ana (autônoma)')
  expect(optionLabels).toContain('Dr. Bruno (vinculado c1)')

  await user.selectOptions(screen.getByLabelText('Clínica solicitante'), 'Clínica Norte')
  const optionLabelsAfter = Array.from(vetSelect.options).map((option) => option.text)
  expect(optionLabelsAfter).toContain('Dra. Ana (autônoma)')
  expect(optionLabelsAfter).not.toContain('Dr. Bruno (vinculado c1)')
})

test('submit is disabled until clinic, veterinarian and patient are all set', async () => {
  const user = userEvent.setup()
  renderPage(['attendances.create'], [patientSearchHandler([bidu()])])

  await screen.findByRole('option', { name: 'Clínica Central' })
  expect(screen.getByRole('button', { name: 'Criar rascunho' })).toBeDisabled()

  await user.selectOptions(screen.getByLabelText('Clínica solicitante'), 'Clínica Central')
  await user.selectOptions(screen.getByLabelText('Veterinário responsável'), 'Dr. Bruno (vinculado c1)')
  expect(screen.getByRole('button', { name: 'Criar rascunho' })).toBeDisabled()

  await user.type(screen.getByLabelText('Paciente'), 'Bidu')
  await user.click(await screen.findByRole('option', { name: /Bidu/ }))

  expect(screen.getByRole('button', { name: 'Criar rascunho' })).toBeEnabled()
})

test('creates a draft and navigates back to the attendance list', async () => {
  const user = userEvent.setup()
  const onDraftCreated = vi.fn()
  server.use(
    http.post('/api/v1/attendances/drafts', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      onDraftCreated(body)
      return HttpResponse.json(
        {
          id: 'a1',
          clinic_id: body.clinic_id,
          veterinarian_id: body.veterinarian_id,
          patient_id: body.patient_id,
          service_date: body.service_date,
          notes: body.notes,
          status: 'DRAFT',
          items: [],
          billing_competence: null,
          subtotal: '0.00',
          discount_total: '0.00',
          surcharge_total: '0.00',
          grand_total: '0.00',
          protocol_number: null,
          cancel_reason: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
        },
        { status: 201 },
      )
    }),
  )
  renderPage(['attendances.create'], [patientSearchHandler([bidu()])])

  await screen.findByRole('option', { name: 'Clínica Central' })
  await user.selectOptions(screen.getByLabelText('Clínica solicitante'), 'Clínica Central')
  await user.selectOptions(screen.getByLabelText('Veterinário responsável'), 'Dr. Bruno (vinculado c1)')
  await user.type(screen.getByLabelText('Paciente'), 'Bidu')
  await user.click(await screen.findByRole('option', { name: /Bidu/ }))
  await user.click(screen.getByRole('button', { name: 'Criar rascunho' }))

  await waitFor(() => expect(onDraftCreated).toHaveBeenCalledTimes(1))
  expect(onDraftCreated).toHaveBeenCalledWith(
    expect.objectContaining({ clinic_id: 'c1', veterinarian_id: 'v2', patient_id: 'p1' }),
  )
  expect(await screen.findByText('Lista de atendimentos')).toBeInTheDocument()
})

test('quick-creates a patient without losing the already-filled clinic/veterinarian', async () => {
  const user = userEvent.setup()
  server.use(
    http.post('/api/v1/patients', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      return HttpResponse.json(
        {
          id: 'p2',
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
    }),
    http.get('/api/v1/species', () =>
      HttpResponse.json({ items: [{ id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' }] }),
    ),
  )
  renderPage(['attendances.create', 'patients.manage'], [patientSearchHandler([])])

  await screen.findByRole('option', { name: 'Clínica Central' })
  await user.selectOptions(screen.getByLabelText('Clínica solicitante'), 'Clínica Central')
  await user.selectOptions(screen.getByLabelText('Veterinário responsável'), 'Dr. Bruno (vinculado c1)')
  await user.type(screen.getByLabelText('Paciente'), 'Thor')

  await user.click(await screen.findByRole('button', { name: /Cadastrar “Thor” como novo paciente/ }))
  await user.type(screen.getByLabelText('Nome do paciente'), 'Thor')
  await user.selectOptions(await screen.findByLabelText('Espécie'), 'Canino')
  await user.type(screen.getByLabelText('Nome do tutor'), 'Marcelo Andrade')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: 'Novo paciente' })).not.toBeInTheDocument(),
  )
  expect(screen.getByText('Thor')).toBeInTheDocument()
  // Clínica/veterinário continuam preenchidos — o rascunho não se perdeu.
  expect(screen.getByLabelText('Clínica solicitante')).toHaveValue('c1')
  expect(screen.getByLabelText('Veterinário responsável')).toHaveValue('v2')
})
