import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { expect, test, vi } from 'vitest'

import { HomePage } from './home-page'

vi.mock('../features/auth/auth-context', () => ({
  useAuth: () => ({
    user: {
      fullName: 'Fabianna Garcia',
      permissions: ['attendances.read', 'attendances.create'],
    },
  }),
}))

vi.mock('../features/attendances/api/use-attendances-query', () => ({
  useAttendancesQuery: () => ({
    isLoading: false,
    isError: false,
    data: { items: [], total: 0, page: 1, pageSize: 5 },
  }),
}))

test('renders the operational dashboard with truthful empty data', () => {
  render(<HomePage />, { wrapper: MemoryRouter })

  expect(screen.getByRole('heading', { name: 'Bom dia, Fabianna.' })).toBeInTheDocument()
  expect(screen.getByText('Nenhum protocolo registrado hoje.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Novo protocolo/ })).toHaveAttribute(
    'href',
    '/operacao/novo',
  )
})
