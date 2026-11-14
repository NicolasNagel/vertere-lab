import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { Modal } from './modal'

function Harness({ canDismiss = true }: { canDismiss?: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Abrir
      </button>
      {open && (
        <Modal titleId="t" canDismiss={canDismiss} dismissOnBackdrop onClose={() => setOpen(false)}>
          <h2 id="t">Título</h2>
          <input aria-label="Campo" />
          <button type="button">Confirmar</button>
        </Modal>
      )}
    </>
  )
}

describe('Modal', () => {
  it('foca o primeiro campo, prende o Tab, fecha com Escape e devolve o foco', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const opener = screen.getByRole('button', { name: 'Abrir' })

    await user.click(opener)
    const dialog = screen.getByRole('dialog', { name: 'Título' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByLabelText('Campo')).toHaveFocus()

    await user.tab()
    expect(screen.getByRole('button', { name: 'Confirmar' })).toHaveFocus()
    await user.tab()
    expect(screen.getByLabelText('Campo')).toHaveFocus()
    await user.tab({ shift: true })
    expect(screen.getByRole('button', { name: 'Confirmar' })).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('não fecha por Escape nem clique no fundo quando canDismiss é false', async () => {
    const user = userEvent.setup()
    render(<Harness canDismiss={false} />)
    await user.click(screen.getByRole('button', { name: 'Abrir' }))

    await user.keyboard('{Escape}')
    await user.pointer({ target: screen.getByRole('dialog').parentElement!, keys: '[MouseLeft]' })
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
})
