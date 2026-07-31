import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Pagination } from './pagination'

describe('Pagination', () => {
  it('shows the server range and changes pages without leaving valid bounds', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()

    render(
      <Pagination
        itemLabel={['registro', 'registros']}
        page={2}
        pageSize={25}
        total={61}
        onPageChange={onPageChange}
      />,
    )

    expect(screen.getByText('26–50 de 61 registros')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Página anterior' }))
    await user.click(screen.getByRole('button', { name: 'Próxima página' }))
    expect(onPageChange).toHaveBeenNthCalledWith(1, 1)
    expect(onPageChange).toHaveBeenNthCalledWith(2, 3)
  })

  it('disables both controls for an empty result', () => {
    render(
      <Pagination
        itemLabel={['registro', 'registros']}
        page={1}
        pageSize={25}
        total={0}
        onPageChange={() => undefined}
      />,
    )

    expect(screen.getByText('Nenhum registro')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Página anterior' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Próxima página' })).toBeDisabled()
  })
})
