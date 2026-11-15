import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'

import type { Exam, ExamCategory } from '../../catalog/api/catalog-api'
import type { DraftExamSelection } from '../api/use-attendance-exam-selections'
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

function selection(target: Exam, overrides: Partial<DraftExamSelection> = {}): DraftExamSelection {
  return { exam: target, quantity: 1, discountAmount: '', overrideReason: '', ...overrides }
}

interface GridOptions {
  selections?: DraftExamSelection[]
  patientSpeciesId?: string | null
  showMoney?: boolean
  canDiscount?: boolean
}

function renderGrid({
  selections = [],
  patientSpeciesId = null,
  showMoney = true,
  canDiscount = true,
}: GridOptions = {}) {
  const onAdd = vi.fn()
  const onRemove = vi.fn()
  const onUpdate = vi.fn()
  render(
    <ExamCartGrid
      exams={[alt, fa, cat, basico]}
      categories={categories}
      selections={selections}
      showMoney={showMoney}
      canDiscount={canDiscount}
      patientSpeciesId={patientSpeciesId}
      isLoading={false}
      isError={false}
      disabled={false}
      onAdd={onAdd}
      onRemove={onRemove}
      onUpdate={onUpdate}
    />,
  )
  return { onAdd, onRemove, onUpdate }
}

test('groups exams by category with panels first and shows the panel composition', () => {
  renderGrid()
  const groups = screen.getAllByRole('region').map((region) => region.getAttribute('aria-label'))
  expect(groups).toEqual(['Perfis', 'Bioquímica'])
  expect(screen.getByText('ALT, FA')).toBeInTheDocument()
})

test('checking adds, unchecking removes, and only the patient species is listed', async () => {
  const user = userEvent.setup()
  const { onAdd, onRemove } = renderGrid({ selections: [selection(alt)], patientSpeciesId: 'dog' })

  expect(screen.queryByRole('checkbox', { name: /Exame de gato/ })).not.toBeInTheDocument()
  await user.click(screen.getByRole('checkbox', { name: /FA/ }))
  expect(onAdd).toHaveBeenCalledWith(fa)
  await user.click(screen.getByRole('checkbox', { name: /ALT/ }))
  expect(onRemove).toHaveBeenCalledWith('alt')
})

test('an exam that is also inside a selected panel is not flagged, repeating is free', () => {
  renderGrid({ selections: [selection(basico), selection(alt)] })
  expect(screen.queryByText(/incluso em/i)).not.toBeInTheDocument()
})

test('a checked exam shows quantity and discount inline, and the discount never exceeds the line value', async () => {
  const { onUpdate } = renderGrid({ selections: [selection(alt, { quantity: 2 })] })

  fireEvent.change(screen.getByLabelText('Quantidade de ALT'), { target: { value: '3' } })
  expect(onUpdate).toHaveBeenLastCalledWith('alt', { quantity: 3 })

  fireEvent.change(screen.getByLabelText('Desconto de ALT'), { target: { value: '5' } })
  expect(onUpdate).toHaveBeenLastCalledWith('alt', { discountAmount: '5' })

  // Linha de 2 x R$ 10,00 = R$ 20,00: 50 é reduzido para o valor da linha.
  fireEvent.change(screen.getByLabelText('Desconto de ALT'), { target: { value: '50' } })
  expect(onUpdate).toHaveBeenLastCalledWith('alt', { discountAmount: '20.00' })
})

test('the discount reason appears only when a discount is set', () => {
  renderGrid({ selections: [selection(alt, { discountAmount: '5' })] })
  expect(screen.getByLabelText('Motivo do desconto de ALT')).toBeInTheDocument()
})

test('without pricing.read there is no price or discount; without override_price only quantity', () => {
  const { onUpdate } = renderGrid({ selections: [selection(alt)], showMoney: false })
  expect(screen.queryByText(/R\$/)).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Desconto de ALT')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Quantidade de ALT')).toBeInTheDocument()
  expect(onUpdate).not.toHaveBeenCalled()
})

test('with pricing.read but no override_price the discount is not offered', () => {
  renderGrid({ selections: [selection(alt)], canDiscount: false })
  expect(screen.getAllByText(/R\$\s*10,00/).length).toBeGreaterThan(0)
  expect(screen.queryByLabelText('Desconto de ALT')).not.toBeInTheDocument()
})
