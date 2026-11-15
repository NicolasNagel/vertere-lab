import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { MemoryRouter } from 'react-router'
import { pickOption } from '../../../test/dropdown'
import { ExamsPage } from './exams-page'

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
        role_name: 'FINANCE',
      },
      permissions,
    }),
  )
}

const urgency = {
  id: 'u',
  fee_amount: '30.00',
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 3,
}

const rule = {
  id: 'r1',
  clinic_id: 'c1',
  name: 'Taxa de coleta',
  fee_amount: '5.00',
  valid_from: '2026-01-01',
  valid_to: null,
  is_active: true,
  exam_ids: [],
  attendance_types: [],
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 1,
}

const hemograma = {
  id: 'e1',
  code: 'HEM001',
  name: 'Hemograma completo',
  category_id: 'cat1',
  description: null,
  species_ids: [],
  status: 'ACTIVE',
  row_version: 1,
  is_panel: false,
  component_exam_ids: [],
  price_base: '85.00',
  updated_at: '2026-06-01T00:00:00Z',
}

function clinicsHandler() {
  return http.get('/api/v1/clinics', () =>
    HttpResponse.json({
      items: [
        {
          id: 'c1',
          name: 'Clínica Alfa',
          status: 'ACTIVE',
          row_version: 1,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    }),
  )
}

// A aba de taxas vive dentro de Exames & Preços; estas rotas só alimentam a tela em volta.
function pageHandlers() {
  return [
    http.get('/api/v1/exams', () =>
      HttpResponse.json({ items: [hemograma], total: 1, page: 1, page_size: 100 }),
    ),
    http.get('/api/v1/species', () => HttpResponse.json({ items: [] })),
    http.get('/api/v1/exam-categories/active', () => HttpResponse.json({ items: [] })),
  ]
}

function renderTab() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter>
          <ExamsPage />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('urgency register shows the fixed value and saves with reason and row version', async () => {
  const user = userEvent.setup()
  let body: unknown = null
  server.use(
    ...pageHandlers(),
    meHandler(['pricing.read', 'pricing.manage']),
    http.get('/api/v1/on-call-fee-settings', () => HttpResponse.json({ items: [] })),
    http.get('/api/v1/urgency-fee-setting', () => HttpResponse.json(urgency)),
    http.patch('/api/v1/urgency-fee-setting', async ({ request }) => {
      body = await request.json()
      return HttpResponse.json({
        ...urgency,
        fee_amount: '40.00',
        row_version: 4,
      })
    }),
  )
  renderTab()

  await user.click(await screen.findByRole('tab', { name: 'Urgência' }))
  expect(await screen.findByText('R$ 30,00')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Ações para Urgência' }))
  await user.click(screen.getByRole('menuitem', { name: 'Editar taxa' }))
  const amount = screen.getByLabelText('Valor da taxa (R$)')
  await user.clear(amount)
  await user.type(amount, '40')
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Reajuste')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(body).not.toBeNull())
  expect(body).toEqual({
    fee_amount: '40.00',
    reason: 'Reajuste',
    expected_row_version: 3,
  })
})

test('clinic register lists rules and creates one with validity and reason', async () => {
  const user = userEvent.setup()
  let created: unknown = null
  server.use(
    ...pageHandlers(),
    meHandler(['pricing.read', 'pricing.manage']),
    http.get('/api/v1/on-call-fee-settings', () => HttpResponse.json({ items: [] })),
    clinicsHandler(),
    http.get('/api/v1/clinic-fee-rules', () => HttpResponse.json({ items: [rule] })),
    http.post('/api/v1/clinic-fee-rules', async ({ request }) => {
      created = await request.json()
      return HttpResponse.json({
        ...rule,
        id: 'r2',
        name: 'Taxa nova',
        fee_amount: '7.50',
      })
    }),
  )
  renderTab()

  await user.click(await screen.findByRole('tab', { name: 'Por clínica' }))
  expect(await screen.findByText('Taxa de coleta')).toBeInTheDocument()
  expect(screen.getByText('R$ 5,00')).toBeInTheDocument()
  expect(screen.getByText('Ativa')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /nova taxa/i }))
  await screen.findByRole('dialog')
  await pickOption(user, 'Clínica', 'Clínica Alfa', await screen.findByRole('dialog'))
  await user.type(screen.getByLabelText('Nome da taxa'), 'Taxa nova')
  await user.type(screen.getByLabelText('Valor (R$)'), '7,5')
  await user.type(screen.getByLabelText('Vale a partir de'), '2026-02-01')
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Contrato novo')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(created).not.toBeNull())
  expect(created).toEqual({
    clinic_id: 'c1',
    name: 'Taxa nova',
    fee_amount: '7.50',
    valid_from: '2026-02-01',
    valid_to: null,
    exam_ids: [],
    attendance_types: [],
    reason: 'Contrato novo',
  })
})

test('urgency register has no days or hours, only the fixed value', async () => {
  const user = userEvent.setup()
  server.use(
    ...pageHandlers(),
    meHandler(['pricing.read', 'pricing.manage']),
    http.get('/api/v1/on-call-fee-settings', () => HttpResponse.json({ items: [] })),
    http.get('/api/v1/urgency-fee-setting', () => HttpResponse.json(urgency)),
  )
  renderTab()

  await user.click(await screen.findByRole('tab', { name: 'Urgência' }))
  await screen.findByText('R$ 30,00')
  expect(screen.queryByRole('columnheader', { name: /dias/i })).not.toBeInTheDocument()
  expect(screen.queryByRole('columnheader', { name: /horário/i })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Ações para Urgência' }))
  await user.click(screen.getByRole('menuitem', { name: 'Editar taxa' }))
  expect(screen.queryByText('Dias da semana')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Horário de início')).not.toBeInTheDocument()
})

test('a clinic rule is created with exam and attendance-type conditions', async () => {
  const user = userEvent.setup()
  let created: unknown = null
  server.use(
    ...pageHandlers(),
    meHandler(['pricing.read', 'pricing.manage']),
    http.get('/api/v1/on-call-fee-settings', () => HttpResponse.json({ items: [] })),
    clinicsHandler(),
    http.get('/api/v1/clinic-fee-rules', () => HttpResponse.json({ items: [rule] })),
    http.post('/api/v1/clinic-fee-rules', async ({ request }) => {
      created = await request.json()
      return HttpResponse.json({ ...rule, id: 'r3' })
    }),
  )
  renderTab()

  await user.click(await screen.findByRole('tab', { name: 'Por clínica' }))
  await user.click(await screen.findByRole('button', { name: /nova taxa/i }))
  const dialog = await screen.findByRole('dialog')
  await pickOption(user, 'Clínica', 'Clínica Alfa', dialog)
  await user.type(screen.getByLabelText('Nome da taxa'), 'Urgente com hemograma')
  await user.type(screen.getByLabelText('Valor (R$)'), '9')
  await user.type(screen.getByLabelText('Vale a partir de'), '2026-02-01')
  await user.click(within(dialog).getByRole('button', { name: 'Urgente' }))
  await user.click(within(dialog).getByRole('button', { name: 'Plantão normal' }))
  await pickOption(user, 'Adicionar exame', 'Hemograma completo', dialog)
  expect(within(dialog).getByRole('button', { name: 'Remover Hemograma completo' })).toBeVisible()
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Acordo')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(created).not.toBeNull())
  expect(created).toMatchObject({
    exam_ids: ['e1'],
    attendance_types: ['URGENTE', 'PLANTAO_NORMAL'],
    fee_amount: '9.00',
  })
})

test('the clinic rule row and popover show the conditions in short form', async () => {
  const user = userEvent.setup()
  server.use(
    ...pageHandlers(),
    meHandler(['pricing.read', 'pricing.manage']),
    http.get('/api/v1/on-call-fee-settings', () => HttpResponse.json({ items: [] })),
    clinicsHandler(),
    http.get('/api/v1/clinic-fee-rules', () =>
      HttpResponse.json({
        items: [
          { ...rule, exam_ids: ['e1'], attendance_types: ['URGENTE', 'PLANTAO_NORMAL'] },
          { ...rule, id: 'r9', name: 'Taxa geral' },
        ],
      }),
    ),
  )
  renderTab()

  await user.click(await screen.findByRole('tab', { name: 'Por clínica' }))
  expect(await screen.findByText('Hemograma completo · Urgente ou Plantão normal')).toBeVisible()
  expect(screen.getByText('Todos os atendimentos')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Taxa de coleta' }))
  const summary = within(await screen.findByRole('dialog'))
  expect(summary.getByText('Condições')).toBeVisible()
  expect(summary.getByText('Hemograma completo · Urgente ou Plantão normal')).toBeVisible()
})

test('without pricing.manage the registers are read-only', async () => {
  server.use(
    ...pageHandlers(),
    meHandler(['pricing.read']),
    http.get('/api/v1/on-call-fee-settings', () => HttpResponse.json({ items: [] })),
    clinicsHandler(),
    http.get('/api/v1/clinic-fee-rules', () => HttpResponse.json({ items: [rule] })),
  )
  const user = userEvent.setup()
  renderTab()
  await user.click(await screen.findByRole('tab', { name: 'Por clínica' }))
  expect(await screen.findByText('Taxa de coleta')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /nova taxa/i })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /editar/i })).not.toBeInTheDocument()
})

test('clicking a fee row opens the summary popover with the edit action', async () => {
  const user = userEvent.setup()
  server.use(
    ...pageHandlers(),
    meHandler(['pricing.read', 'pricing.manage']),
    http.get('/api/v1/on-call-fee-settings', () => HttpResponse.json({ items: [] })),
    clinicsHandler(),
    http.get('/api/v1/clinic-fee-rules', () => HttpResponse.json({ items: [rule] })),
  )
  renderTab()

  await user.click(await screen.findByRole('tab', { name: 'Por clínica' }))
  await user.click(await screen.findByRole('button', { name: 'Taxa de coleta' }))
  const summary = within(await screen.findByRole('dialog'))
  expect(summary.getByRole('heading', { name: 'Taxa de coleta' })).toBeInTheDocument()
  expect(summary.getByText('R$ 5,00')).toBeInTheDocument()
  await user.click(summary.getByRole('button', { name: 'Editar taxa' }))
  expect(await screen.findByLabelText('Nome da taxa')).toHaveValue('Taxa de coleta')
})
