import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { FeesTab } from './fees-tab'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function meHandler(permissions: string[]) {
  return http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      user: { id: 'u1', email: 'a@b.com', full_name: 'A', role_id: 'r1', role_name: 'FINANCE' },
      permissions,
    }),
  )
}

const urgency = {
  id: 'u',
  fee_amount: '30.00',
  schedule_label: '',
  weekdays: [],
  start_time: null,
  end_time: null,
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
  updated_at: '2026-01-01T00:00:00Z',
  row_version: 1,
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

function renderTab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <FeesTab />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('urgency register shows the fixed value and saves with reason and row version', async () => {
  const user = userEvent.setup()
  let body: unknown = null
  server.use(
    meHandler(['pricing.read', 'pricing.manage']),
    http.get('/api/v1/on-call-fee-settings', () => HttpResponse.json({ items: [] })),
    http.get('/api/v1/urgency-fee-setting', () => HttpResponse.json(urgency)),
    http.patch('/api/v1/urgency-fee-setting', async ({ request }) => {
      body = await request.json()
      return HttpResponse.json({ ...urgency, fee_amount: '40.00', row_version: 4 })
    }),
  )
  renderTab()

  await user.click(await screen.findByRole('tab', { name: 'Urgência' }))
  expect(await screen.findByText('R$ 30,00')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Editar taxa de urgência' }))
  const amount = screen.getByLabelText('Valor da taxa (R$)')
  await user.clear(amount)
  await user.type(amount, '40')
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Reajuste')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(body).not.toBeNull())
  expect(body).toEqual({
    fee_amount: '40.00',
    weekdays: [],
    start_time: null,
    end_time: null,
    reason: 'Reajuste',
    expected_row_version: 3,
  })
})

test('clinic register lists rules and creates one with validity and reason', async () => {
  const user = userEvent.setup()
  let created: unknown = null
  server.use(
    meHandler(['pricing.read', 'pricing.manage']),
    http.get('/api/v1/on-call-fee-settings', () => HttpResponse.json({ items: [] })),
    clinicsHandler(),
    http.get('/api/v1/clinic-fee-rules', () => HttpResponse.json({ items: [rule] })),
    http.post('/api/v1/clinic-fee-rules', async ({ request }) => {
      created = await request.json()
      return HttpResponse.json({ ...rule, id: 'r2', name: 'Taxa nova', fee_amount: '7.50' })
    }),
  )
  renderTab()

  await user.click(await screen.findByRole('tab', { name: 'Por clínica' }))
  expect(await screen.findByText('Taxa de coleta')).toBeInTheDocument()
  expect(screen.getByText('R$ 5,00')).toBeInTheDocument()
  expect(screen.getByText('Ativa')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /nova taxa/i }))
  await screen.findByRole('dialog')
  await user.selectOptions(screen.getByLabelText('Clínica'), 'c1')
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
    reason: 'Contrato novo',
  })
})

test('without pricing.manage the registers are read-only', async () => {
  server.use(
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
