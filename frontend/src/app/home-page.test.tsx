import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, test, vi } from 'vitest'

import { greetingFor } from './greeting'
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

vi.mock('../features/attendances/api/use-attendance-status-counts-query', () => ({
  useAttendanceStatusCountsQuery: () => ({
    isLoading: false,
    data: { total: 8, byStatus: { CONFIRMED: 7, DRAFT: 1 }, billedTotal: '1234.56' },
  }),
}))

afterEach(() => vi.useRealTimers())

test('greets by the time of day', () => {
  expect(greetingFor(new Date(2026, 0, 5, 8))).toBe('Bom dia')
  expect(greetingFor(new Date(2026, 0, 5, 12))).toBe('Boa tarde')
  expect(greetingFor(new Date(2026, 0, 5, 18))).toBe('Boa noite')
})

test('renders the operational dashboard with truthful empty data and the server billed total', () => {
  vi.useFakeTimers({ toFake: ['Date'], now: new Date(2026, 0, 5, 9) })
  render(<HomePage />, { wrapper: MemoryRouter })

  expect(screen.getByRole('heading', { name: 'Bom dia, Fabianna.' })).toBeInTheDocument()
  expect(screen.getByText('Nenhum protocolo registrado hoje.')).toBeInTheDocument()
  // O valor vem do servidor para o dia inteiro, não da soma dos 5 itens exibidos.
  expect(screen.getByText(/1\.234,56/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Novo protocolo/ })).toHaveAttribute(
    'href',
    '/operacao/novo',
  )
})
