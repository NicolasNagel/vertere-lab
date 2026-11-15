import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { OnCallFeeSettingsPanel } from './on-call-fee-settings-panel'

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

function settingsHandler() {
  return http.get('/api/v1/on-call-fee-settings', () =>
    HttpResponse.json({
      items: [
        {
          id: 's1',
          service_level: 'PLANTAO_NORMAL',
          fee_amount: '100.00',
          schedule_label: '',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
        },
        {
          id: 's2',
          service_level: 'PLANTAO_ESPECIAL',
          fee_amount: '150.00',
          schedule_label: '',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
        },
      ],
    }),
  )
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    (
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <OnCallFeeSettingsPanel />
        </AuthProvider>
      </QueryClientProvider>
    ) as ReactNode,
  )
}

test('the panel is gated by pricing.read and read-only without pricing.manage', async () => {
  server.use(meHandler([]), settingsHandler())
  let view = renderPanel()
  expect(await screen.findByText('Você não tem permissão para ver as taxas.')).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  server.use(meHandler(['pricing.read']), settingsHandler())
  view = renderPanel()
  expect(await screen.findByText('Plantão normal')).toBeInTheDocument()
  expect(screen.getByText('Plantão especial / noturno')).toBeInTheDocument()
  expect(screen.getByText('R$ 100,00')).toBeInTheDocument()
  expect(screen.getByText('R$ 150,00')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /editar/i })).not.toBeInTheDocument()
})

test('editing needs a reason, sends the row version and a conflict offers reload', async () => {
  const user = userEvent.setup()
  let receivedBody: unknown = null
  server.use(
    meHandler(['pricing.read', 'pricing.manage']),
    settingsHandler(),
    http.patch('/api/v1/on-call-fee-settings/PLANTAO_NORMAL', async ({ request }) => {
      receivedBody = await request.json()
      return HttpResponse.json({
        id: 's1',
        service_level: 'PLANTAO_NORMAL',
        fee_amount: '120.00',
        schedule_label: '',
        updated_at: '2026-01-02T00:00:00Z',
        row_version: 2,
      })
    }),
  )
  const view = renderPanel()

  await user.click(await screen.findByRole('button', { name: 'Ações para Plantão normal' }))
  await user.click(screen.getByRole('menuitem', { name: 'Editar taxa' }))
  const amount = screen.getByLabelText('Valor da taxa (R$)')
  await user.clear(amount)
  await user.type(amount, '120,00')
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Reajuste anual')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(receivedBody).not.toBeNull())
  expect(receivedBody).toEqual({
    fee_amount: '120.00',
    weekdays: [],
    start_time: null,
    end_time: null,
    reason: 'Reajuste anual',
    expected_row_version: 1,
  })
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  view.unmount()
  server.resetHandlers()

  server.use(
    meHandler(['pricing.read', 'pricing.manage']),
    settingsHandler(),
    http.patch('/api/v1/on-call-fee-settings/PLANTAO_NORMAL', () =>
      HttpResponse.json(
        {
          error: {
            code: 'CONFLICT',
            message: 'Esta configuração foi alterada por outra pessoa.',
          },
        },
        { status: 409 },
      ),
    ),
  )
  renderPanel()
  await user.click(await screen.findByRole('button', { name: 'Ações para Plantão normal' }))
  await user.click(screen.getByRole('menuitem', { name: 'Editar taxa' }))
  const conflictAmount = screen.getByLabelText('Valor da taxa (R$)')
  await user.clear(conflictAmount)
  await user.type(conflictAmount, '999')
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Teste')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  expect(
    await screen.findByText('Esta configuração foi alterada por outra pessoa.'),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Recarregar' })).toBeInTheDocument()
})

test('edits weekdays and hours, with presets and midnight crossing', async () => {
  const user = userEvent.setup()
  let receivedBody: unknown = null
  server.use(
    meHandler(['pricing.read', 'pricing.manage']),
    settingsHandler(),
    http.patch('/api/v1/on-call-fee-settings/PLANTAO_NORMAL', async ({ request }) => {
      receivedBody = await request.json()
      return HttpResponse.json({
        id: 's1',
        service_level: 'PLANTAO_NORMAL',
        fee_amount: '100.00',
        schedule_label: 'Seg-Sex · 19h às 07h',
        weekdays: [0, 1, 2, 3, 4],
        start_time: '19:00:00',
        end_time: '07:00:00',
        updated_at: '2026-01-02T00:00:00Z',
        row_version: 2,
      })
    }),
  )
  renderPanel()

  await user.click(await screen.findByRole('button', { name: 'Ações para Plantão normal' }))
  await user.click(screen.getByRole('menuitem', { name: 'Editar taxa' }))
  await user.click(screen.getByRole('button', { name: 'Seg-Sex' }))
  expect(screen.getByRole('button', { name: 'Segunda-feira' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  expect(screen.getByRole('button', { name: 'Sábado' })).toHaveAttribute('aria-pressed', 'false')
  await user.click(screen.getByRole('button', { name: 'Sábado' }))
  await user.click(screen.getByRole('button', { name: 'Sábado' }))
  fireEvent.change(screen.getByLabelText('Horário de início'), { target: { value: '19:00' } })
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  expect(await screen.findByText('Informe o horário de início e o de fim.')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Horário de fim'), { target: { value: '19:00' } })
  expect(
    await screen.findByText('O horário de fim deve ser diferente do início.'),
  ).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Horário de fim'), { target: { value: '07:00' } })
  expect(screen.getByText(/vira a meia-noite/)).toBeInTheDocument()
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Definir plantão')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(receivedBody).not.toBeNull())
  expect(receivedBody).toEqual({
    fee_amount: '100.00',
    weekdays: [0, 1, 2, 3, 4],
    start_time: '19:00',
    end_time: '07:00',
    reason: 'Definir plantão',
    expected_row_version: 1,
  })
})
