import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactElement } from 'react'
import { afterAll, afterEach, beforeAll, expect, test, vi } from 'vitest'

import { ClinicForm } from './clinic-form'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderForm(element: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{element}</QueryClientProvider>)
}

function cepHandler(
  body: Record<string, unknown> | { error: { code: string; message: string } },
  status = 200,
) {
  return http.get('/api/v1/address-lookup/cep/:cep', () => HttpResponse.json(body, { status }))
}

test('requires a name before allowing submit', async () => {
  const user = userEvent.setup()
  const onSubmitCreate = vi.fn()
  renderForm(
    <ClinicForm
      clinic={null}
      submitting={false}
      onCancel={() => {}}
      onSubmitCreate={onSubmitCreate}
    />,
  )

  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByText('Informe o nome da clínica.')).toBeInTheDocument()
  expect(onSubmitCreate).not.toHaveBeenCalled()
})

test('submits create values with empty optional fields as null', async () => {
  const user = userEvent.setup()
  const onSubmitCreate = vi.fn()
  renderForm(
    <ClinicForm
      clinic={null}
      submitting={false}
      onCancel={() => {}}
      onSubmitCreate={onSubmitCreate}
    />,
  )

  await user.type(screen.getByLabelText('Nome da clínica'), 'Bicho Urbano')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(onSubmitCreate).toHaveBeenCalledWith(
    expect.objectContaining({ name: 'Bicho Urbano', taxId: null, phone: null }),
  )
})

test('does not show the status field when creating a new clinic', () => {
  renderForm(<ClinicForm clinic={null} submitting={false} onCancel={() => {}} />)

  expect(screen.queryByLabelText('Status')).not.toBeInTheDocument()
})

test('shows the status field when editing an existing clinic', () => {
  renderForm(
    <ClinicForm
      clinic={{
        id: '1',
        name: 'Schweitzer',
        taxId: '78977352000199',
        phone: null,
        email: null,
        status: 'ACTIVE',
        addressZipCode: null,
        addressStreet: null,
        addressNumber: null,
        addressNeighborhood: null,
        addressCity: null,
        addressState: null,
        addressComplement: null,
        notes: null,
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-01T00:00:00Z',
        rowVersion: 1,
      }}
      submitting={false}
      onCancel={() => {}}
    />,
  )

  expect(screen.getByLabelText('Status')).toBeInTheDocument()
})

test('disables the submit button while submitting', () => {
  renderForm(<ClinicForm clinic={null} submitting={true} onCancel={() => {}} />)

  expect(screen.getByRole('button', { name: 'Salvando…' })).toBeDisabled()
})

test('fills address fields when a valid CEP is found', async () => {
  const user = userEvent.setup({ delay: null })
  server.use(
    cepHandler({
      zip_code: '01310100',
      street: 'Avenida Paulista',
      neighborhood: 'Bela Vista',
      city: 'São Paulo',
      state: 'SP',
    }),
  )
  renderForm(<ClinicForm clinic={null} submitting={false} onCancel={() => {}} />)

  await user.type(screen.getByLabelText('CEP'), '01310100')

  await waitFor(() => {
    expect(screen.getByLabelText('Rua')).toHaveValue('Avenida Paulista')
  })
  expect(screen.getByLabelText('Bairro')).toHaveValue('Bela Vista')
  expect(screen.getByLabelText('Cidade')).toHaveValue('São Paulo')
  expect(screen.getByLabelText('UF')).toHaveValue('SP')
})

test('shows a message and keeps fields editable when the CEP is not found', async () => {
  const user = userEvent.setup({ delay: null })
  server.use(
    cepHandler({ error: { code: 'NOT_FOUND', message: 'CEP não encontrado.' } }, 404),
  )
  renderForm(<ClinicForm clinic={null} submitting={false} onCancel={() => {}} />)

  await user.type(screen.getByLabelText('CEP'), '00000000')

  expect(
    await screen.findByText('CEP não encontrado. Preencha o endereço manualmente.'),
  ).toBeInTheDocument()
  expect(screen.getByLabelText('Rua')).not.toBeDisabled()
})

test('provider failure does not block manual fill or submit', async () => {
  const user = userEvent.setup({ delay: null })
  const onSubmitCreate = vi.fn()
  server.use(
    cepHandler(
      { error: { code: 'EXTERNAL_SERVICE_UNAVAILABLE', message: 'Serviço indisponível.' } },
      503,
    ),
  )
  renderForm(
    <ClinicForm
      clinic={null}
      submitting={false}
      onCancel={() => {}}
      onSubmitCreate={onSubmitCreate}
    />,
  )

  await user.type(screen.getByLabelText('Nome da clínica'), 'Bicho Urbano')
  await user.type(screen.getByLabelText('CEP'), '01310100')

  expect(
    await screen.findByText('Não foi possível consultar o CEP. Preencha manualmente.'),
  ).toBeInTheDocument()

  await user.type(screen.getByLabelText('Rua'), 'Rua Manual')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(onSubmitCreate).toHaveBeenCalledWith(
    expect.objectContaining({ addressStreet: 'Rua Manual' }),
  )
})
