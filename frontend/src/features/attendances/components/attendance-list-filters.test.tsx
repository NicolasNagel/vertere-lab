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

  await user.selectOptions(screen.getByLabelText('Competência'), '2026-11')
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
