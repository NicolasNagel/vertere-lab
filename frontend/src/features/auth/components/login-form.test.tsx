import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { LoginForm } from './login-form'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>)
}

test('disables the submit button while the request is in flight', async () => {
  const user = userEvent.setup()
  server.use(
    http.post('/api/v1/auth/login', async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
      return HttpResponse.json({
        user: { id: '1', email: 'a@b.com', full_name: 'A', role_id: 'r', role_name: 'LAB_ADMIN' },
        permissions: [],
      })
    }),
  )
  renderWithProviders(<LoginForm />)

  await user.type(screen.getByLabelText('Usuário'), 'reception')
  await user.type(screen.getByLabelText('Senha'), 'correct-password')
  const submitButton = screen.getByRole('button', { name: 'Entrar no sistema' })
  await user.click(submitButton)

  expect(screen.getByRole('button', { name: 'Entrando…' })).toBeDisabled()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Entrar no sistema' })).toBeEnabled())
})

test('shows a generic error for invalid credentials without revealing user existence', async () => {
  const user = userEvent.setup()
  server.use(
    http.post('/api/v1/auth/login', () =>
      HttpResponse.json(
        {
          error: {
            code: 'UNAUTHENTICATED',
            message: 'Usuário ou senha inválidos.',
            request_id: 'req-1',
            details: [],
          },
        },
        { status: 401 },
      ),
    ),
  )
  renderWithProviders(<LoginForm />)

  await user.type(screen.getByLabelText('Usuário'), 'ghost')
  await user.type(screen.getByLabelText('Senha'), 'whatever')
  await user.click(screen.getByRole('button', { name: 'Entrar no sistema' }))

  expect(await screen.findByText('Usuário ou senha inválidos.')).toBeInTheDocument()
})

test('shows a connection failure message when the network request fails', async () => {
  const user = userEvent.setup()
  server.use(
    http.post('/api/v1/auth/login', () => HttpResponse.error()),
  )
  renderWithProviders(<LoginForm />)

  await user.type(screen.getByLabelText('Usuário'), 'reception')
  await user.type(screen.getByLabelText('Senha'), 'correct-password')
  await user.click(screen.getByRole('button', { name: 'Entrar no sistema' }))

  expect(await screen.findByText('Falha de conexão. Verifique sua internet e tente novamente.')).toBeInTheDocument()
})

test('requires both fields before allowing submission', async () => {
  const user = userEvent.setup()
  renderWithProviders(<LoginForm />)

  await user.click(screen.getByRole('button', { name: 'Entrar no sistema' }))

  expect(await screen.findByText('Informe seu usuário ou e-mail.')).toBeInTheDocument()
  expect(screen.getByText('Informe sua senha.')).toBeInTheDocument()
})

test('toggles the password field visibility', async () => {
  const user = userEvent.setup()
  renderWithProviders(<LoginForm />)

  const passwordInput = screen.getByLabelText('Senha')
  expect(passwordInput).toHaveAttribute('type', 'password')

  await user.click(screen.getByRole('button', { name: 'Mostrar senha' }))
  expect(passwordInput).toHaveAttribute('type', 'text')

  await user.click(screen.getByRole('button', { name: 'Ocultar senha' }))
  expect(passwordInput).toHaveAttribute('type', 'password')
})

test('shows an explicit not-implemented notice for forgot password instead of failing silently', async () => {
  const user = userEvent.setup()
  renderWithProviders(<LoginForm />)

  expect(
    screen.queryByText(/recuperação de senha por conta própria ainda não está disponível/i),
  ).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Esqueci a senha' }))

  expect(
    screen.getByText(/recuperação de senha por conta própria ainda não está disponível/i),
  ).toBeInTheDocument()
})

test('renders a contact link for administrator help instead of dead text', () => {
  renderWithProviders(<LoginForm />)

  const helpLink = screen.getByRole('link', { name: 'Fale com o administrador.' })
  expect(helpLink).toHaveAttribute('href', expect.stringMatching(/^mailto:/))
})
