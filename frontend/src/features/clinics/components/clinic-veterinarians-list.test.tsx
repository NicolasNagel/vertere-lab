import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'

import type { ClinicLinkedVeterinarian } from '../api/clinics-api'
import { ClinicVeterinariansList } from './clinic-veterinarians-list'

function vets(count: number): ClinicLinkedVeterinarian[] {
  return Array.from({ length: count }, (_, index) => ({
    veterinarianId: `v${index}`,
    veterinarianName: `Dr(a). Nome ${String(index).padStart(2, '0')}`,
    crmv: `CRMV-SC ${20100 + index}`,
    primaryClinic: index === 0,
  }))
}

test('shows an empty message when nobody is linked', () => {
  render(<ClinicVeterinariansList veterinarians={[]} />)
  expect(screen.getByText('Nenhum veterinário vinculado ainda.')).toBeInTheDocument()
})

test('a short list shows everyone and no "Ver todos" button', () => {
  render(<ClinicVeterinariansList veterinarians={vets(5)} />)
  expect(screen.getAllByRole('listitem')).toHaveLength(5)
  expect(screen.queryByRole('button', { name: /Ver todos/ })).not.toBeInTheDocument()
})

test('a long list shows a 5-row preview, then expands into a searchable, bounded list', async () => {
  const user = userEvent.setup()
  render(<ClinicVeterinariansList veterinarians={vets(20)} />)

  expect(screen.getAllByRole('listitem')).toHaveLength(5)
  expect(screen.queryByLabelText('Buscar veterinário vinculado')).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Ver todos (20)' }))
  expect(within(screen.getByRole('list', { name: 'Veterinários vinculados' })).getAllByRole('listitem')).toHaveLength(20)
  expect(screen.getByText('20 de 20 veterinários')).toBeInTheDocument()

  await user.type(screen.getByLabelText('Buscar veterinário vinculado'), 'nome 07')
  expect(screen.getByText('1 de 20 veterinários')).toBeInTheDocument()
  expect(screen.getByText('Dr(a). Nome 07')).toBeInTheDocument()

  await user.clear(screen.getByLabelText('Buscar veterinário vinculado'))
  await user.type(screen.getByLabelText('Buscar veterinário vinculado'), 'CRMV-SC 20119')
  expect(screen.getByText('Dr(a). Nome 19')).toBeInTheDocument()

  await user.clear(screen.getByLabelText('Buscar veterinário vinculado'))
  await user.type(screen.getByLabelText('Buscar veterinário vinculado'), 'inexistente')
  expect(screen.getByText('Nenhum veterinário encontrado.')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Mostrar menos' }))
  expect(screen.getAllByRole('listitem')).toHaveLength(5)
  expect(screen.getByRole('button', { name: 'Ver todos (20)' })).toBeInTheDocument()
})
