import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'

import { ClinicForm } from './clinic-form'

test('requires a name before allowing submit', async () => {
  const user = userEvent.setup()
  const onSubmitCreate = vi.fn()
  render(
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
  render(
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
  render(<ClinicForm clinic={null} submitting={false} onCancel={() => {}} />)

  expect(screen.queryByLabelText('Status')).not.toBeInTheDocument()
})

test('shows the status field when editing an existing clinic', () => {
  render(
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
  render(<ClinicForm clinic={null} submitting={true} onCancel={() => {}} />)

  expect(screen.getByRole('button', { name: 'Salvando…' })).toBeDisabled()
})
