import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'

import { AttendanceListFilters } from './attendance-list-filters'

function renderFilters(overrides: { clinicId?: string; serviceLevel?: '' | 'NORMAL' } = {}) {
  const handlers = {
    onClinicChange: vi.fn(),
    onServiceLevelChange: vi.fn(),
    onServiceDateFromChange: vi.fn(),
    onServiceDateToChange: vi.fn(),
  }
  render(
    <AttendanceListFilters
      clinicOptions={[{ value: 'c1', label: 'Clínica Um' }]}
      clinicId={overrides.clinicId ?? ''}
      serviceLevel={overrides.serviceLevel ?? ''}
      disabled={false}
      {...handlers}
    />,
  )
  return handlers
}

test('"Limpar filtros" only shows with an active filter and resets period, clinic and type', async () => {
  const user = userEvent.setup()
  const handlers = renderFilters({ clinicId: 'c1', serviceLevel: 'NORMAL' })

  await user.click(screen.getByRole('button', { name: /Competência/ }))
  await user.click(screen.getByRole('option', { name: 'Nov 2026' }))
  expect(handlers.onServiceDateFromChange).toHaveBeenLastCalledWith('2026-11-01')
  expect(handlers.onServiceDateToChange).toHaveBeenLastCalledWith('2026-11-30')
  await user.click(screen.getByRole('button', { name: 'Limpar filtros' }))

  expect(handlers.onClinicChange).toHaveBeenLastCalledWith('')
  expect(handlers.onServiceLevelChange).toHaveBeenLastCalledWith('')
  expect(handlers.onServiceDateFromChange).toHaveBeenLastCalledWith('')
  expect(handlers.onServiceDateToChange).toHaveBeenLastCalledWith('')
})

test('without active filters there is nothing to clear', () => {
  renderFilters()
  expect(screen.queryByRole('button', { name: 'Limpar filtros' })).not.toBeInTheDocument()
})

test('clinic dropdown filters by search and selects with the keyboard', async () => {
  const user = userEvent.setup()
  const handlers = renderFilters()

  await user.click(screen.getByRole('button', { name: /Clínica/ }))
  await user.type(screen.getByRole('combobox', { name: 'Buscar em Clínica' }), 'um')
  expect(screen.getByRole('option', { name: 'Clínica Um' })).toBeInTheDocument()
  expect(screen.queryByRole('option', { name: 'Todas' })).not.toBeInTheDocument()
  await user.keyboard('{Enter}')

  expect(handlers.onClinicChange).toHaveBeenCalledWith('c1')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})

test('Escape closes the dropdown and returns focus to its button', async () => {
  const user = userEvent.setup()
  renderFilters()

  const trigger = screen.getByRole('button', { name: /Tipo/ })
  await user.click(trigger)
  expect(screen.getByRole('listbox', { name: 'Tipo' })).toBeInTheDocument()
  await user.keyboard('{Escape}')

  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})
