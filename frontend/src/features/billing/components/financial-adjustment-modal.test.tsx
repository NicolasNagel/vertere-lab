import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'

import { FinancialAdjustmentModal } from './financial-adjustment-modal'

test('accepts pt-BR amounts, sends the canonical value and blocks invalid ones', async () => {
  const user = userEvent.setup()
  const onConfirm = vi.fn()
  render(
    <FinancialAdjustmentModal
      isPending={false}
      error={null}
      onCancel={() => undefined}
      onConfirm={onConfirm}
    />,
  )
  const submit = screen.getByRole('button', { name: 'Adicionar ajuste' })
  await user.type(screen.getByLabelText('Justificativa'), 'Desconto acordado com a clínica')

  // Valores inválidos mantêm o botão desabilitado.
  for (const invalid of ['0', 'abc', '1,234.56', '10,999']) {
    await user.clear(screen.getByLabelText('Valor'))
    await user.type(screen.getByLabelText('Valor'), invalid)
    expect(submit, invalid).toBeDisabled()
  }

  // "1.234,56" é 1234.56 (antes virava NaN e travava o botão).
  await user.clear(screen.getByLabelText('Valor'))
  await user.type(screen.getByLabelText('Valor'), '1.234,56')
  expect(submit).toBeEnabled()
  await user.click(submit)
  expect(onConfirm).toHaveBeenCalledWith({
    monthlyClosureItemId: null,
    kind: 'DEBIT',
    amount: '1234.56',
    reason: 'Desconto acordado com a clínica',
  })
})
