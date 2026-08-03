import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
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
      user: { id: 'u1', email: 'a@b.com', full_name: 'A', role_id: 'r1', role_name: 'FINANCE' },
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
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <OnCallFeeSettingsPanel />
      </AuthProvider>
    </QueryClientProvider> as ReactNode,
  )
}

test('hides the panel entirely without pricing.read', async () => {
  server.use(meHandler([]), settingsHandler())
  renderPanel()

  await waitFor(() => expect(screen.queryByText('Taxas de plantão')).not.toBeInTheDocument())
})

test('shows both tiers with values from the API', async () => {
  server.use(meHandler(['pricing.read']), settingsHandler())
  renderPanel()

  expect(await screen.findByText('Taxas de plantão')).toBeInTheDocument()
  expect(screen.getByText('Plantão normal')).toBeInTheDocument()
  expect(screen.getByText('Plantão especial / noturno')).toBeInTheDocument()
  expect(screen.getByDisplayValue('100.00')).toBeInTheDocument()
  expect(screen.getByDisplayValue('150.00')).toBeInTheDocument()
})

test('hides the save action and disables inputs without pricing.manage', async () => {
  server.use(meHandler(['pricing.read']), settingsHandler())
  renderPanel()

  await screen.findByText('Taxas de plantão')
  expect(screen.queryByRole('button', { name: /salvar alterações/i })).not.toBeInTheDocument()
  expect(screen.getByDisplayValue('100.00')).toBeDisabled()
})

test('editing a tier and saving sends the updated value with the current row version', async () => {
  server.use(meHandler(['pricing.read', 'pricing.manage']), settingsHandler())
  let receivedBody: unknown = null
  server.use(
    http.patch('/api/v1/on-call-fee-settings/PLANTAO_NORMAL', async ({ request }) => {
      receivedBody = await request.json()
      return HttpResponse.json({
        id: 's1',
        service_level: 'PLANTAO_NORMAL',
        fee_amount: '120.00',
        schedule_label: 'Seg-Sáb - 19h às 07h',
        updated_at: '2026-01-02T00:00:00Z',
        row_version: 2,
      })
    }),
  )
  const user = userEvent.setup()
  renderPanel()

  await screen.findByText('Taxas de plantão')
  const feeInput = screen.getByDisplayValue('100.00')
  await user.clear(feeInput)
  await user.type(feeInput, '120.00')

  await user.click(screen.getByRole('button', { name: /salvar alterações/i }))

  await waitFor(() => expect(receivedBody).not.toBeNull())
  expect(receivedBody).toEqual({
    fee_amount: '120.00',
    schedule_label: '',
    expected_row_version: 1,
  })
  expect(await screen.findByText('Alterações salvas.')).toBeInTheDocument()
})

test('shows a per-tier error message when saving fails', async () => {
  server.use(meHandler(['pricing.read', 'pricing.manage']), settingsHandler())
  server.use(
    http.patch('/api/v1/on-call-fee-settings/PLANTAO_NORMAL', () =>
      HttpResponse.json(
        { error: { code: 'CONFLICT', message: 'Esta configuração foi alterada por outra pessoa.' } },
        { status: 409 },
      ),
    ),
  )
  const user = userEvent.setup()
  renderPanel()

  await screen.findByText('Taxas de plantão')
  const feeInput = screen.getByDisplayValue('100.00')
  await user.clear(feeInput)
  await user.type(feeInput, '999.00')
  await user.click(screen.getByRole('button', { name: /salvar alterações/i }))

  expect(
    await screen.findByText('Esta configuração foi alterada por outra pessoa.'),
  ).toBeInTheDocument()
})
