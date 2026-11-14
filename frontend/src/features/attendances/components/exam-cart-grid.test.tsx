import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'

import type { Exam, ExamCategory } from '../../catalog/api/catalog-api'
import { ExamCartGrid } from './exam-cart-grid'

function exam(id: string, name: string, categoryId: string, overrides: Partial<Exam> = {}): Exam {
  return {
    id,
    code: id.toUpperCase(),
    name,
    categoryId,
    description: null,
    speciesIds: ['dog'],
    componentExamIds: [],
    isPanel: false,
    status: 'ACTIVE',
    rowVersion: 1,
    priceBase: '10.00',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

const categories: ExamCategory[] = [
  { id: 'bio', name: 'Bioquímica', status: 'ACTIVE', rowVersion: 1 },
  { id: 'perfis', name: 'Perfis', status: 'ACTIVE', rowVersion: 1 },
]
const alt = exam('alt', 'ALT', 'bio')
const fa = exam('fa', 'FA', 'bio')
const cat = exam('cat-only', 'Exame de gato', 'bio', { speciesIds: ['cat'] })
const basico = exam('basico', 'BÁSICO 1', 'perfis', {
  isPanel: true,
  componentExamIds: ['alt', 'fa'],
  priceBase: '105.00',
})

function renderGrid(selectedIds: string[], patientSpeciesId: string | null = null) {
  const onAdd = vi.fn()
  const onRemove = vi.fn()
  render(
    <ExamCartGrid
      exams={[alt, fa, cat, basico]}
      categories={categories}
      selectedIds={selectedIds}
      patientSpeciesId={patientSpeciesId}
      isLoading={false}
      isError={false}
      disabled={false}
      onAdd={onAdd}
      onRemove={onRemove}
    />,
  )
  return { onAdd, onRemove }
}

test('groups exams by category with panels first and shows the panel composition', () => {
  renderGrid([])
  const groups = screen.getAllByRole('region').map((region) => region.getAttribute('aria-label'))
  expect(groups).toEqual(['Perfis', 'Bioquímica'])
  expect(screen.getByText('ALT, FA')).toBeInTheDocument()
})

test('checking adds, unchecking removes, and only the patient species is listed', async () => {
  const user = userEvent.setup()
  const { onAdd, onRemove } = renderGrid(['alt'], 'dog')

  expect(screen.queryByRole('checkbox', { name: /Exame de gato/ })).not.toBeInTheDocument()
  await user.click(screen.getByRole('checkbox', { name: /FA/ }))
  expect(onAdd).toHaveBeenCalledWith(fa)
  await user.click(screen.getByRole('checkbox', { name: /ALT/ }))
  expect(onRemove).toHaveBeenCalledWith('alt')
})

test('an exam already inside a selected panel is flagged, and flagged harder when also checked', () => {
  renderGrid(['basico', 'alt'])
  expect(screen.getByText('Já incluso em BÁSICO 1')).toBeInTheDocument()
  expect(screen.getByText('Incluso em BÁSICO 1')).toBeInTheDocument()
})
