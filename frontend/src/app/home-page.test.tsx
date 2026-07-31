import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { expect, test } from 'vitest'

import { HomePage } from './home-page'

test('home page renders the product name', () => {
  render(<HomePage />, { wrapper: MemoryRouter })

  expect(screen.getByRole('heading', { name: 'Vertere Lab' })).toBeInTheDocument()
})
