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
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return {
    ...render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>),
    queryClient,
  }
}

async function fillCredentials(
  user: ReturnType<typeof userEvent.setup>,
  login: string,
  password: string,
) {
  await user.type(screen.getByLabelText('Usuário'), login)
  await user.type(screen.getByLabelText('Senha'), password)
  await user.click(screen.getByRole('button', { name: 'Entrar no sistema' }))
}

test('submits once, disables the button in flight and maps failures without revealing user existence', async () => {
  const user = userEvent.setup()

  // Em andamento: botão desabilitado e uma única mutação bem-sucedida.
  server.use(
    http.post('/api/v1/auth/login', async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
      return HttpResponse.json({
        user: {
          id: '1',
          email: 'a@b.com',
          full_name: 'A',
          role_id: 'r',
          role_name: 'LAB_ADMIN',
        },
        permissions: [],
      })
    }),
  )
  const { queryClient, unmount } = renderWithProviders(<LoginForm />)
  await fillCredentials(user, 'reception', 'correct-password')
  expect(screen.getByRole('button', { name: 'Entrando…' })).toBeDisabled()
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Entrar no sistema' })).toBeEnabled(),
  )
  expect(queryClient.getMutationCache().getAll()).toHaveLength(1)
  expect(queryClient.getMutationCache().getAll()[0]?.state.status).toBe('success')
  unmount()
  server.resetHandlers()

  // Credenciais inválidas: mensagem genérica.
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
  const second = renderWithProviders(<LoginForm />)
  await fillCredentials(user, 'ghost', 'whatever')
  expect(await screen.findByText('Usuário ou senha inválidos.')).toBeInTheDocument()
  second.unmount()
  server.resetHandlers()

  // Falha de rede.
  server.use(http.post('/api/v1/auth/login', () => HttpResponse.error()))
  renderWithProviders(<LoginForm />)
  await fillCredentials(user, 'reception', 'correct-password')
  expect(
    await screen.findByText('Falha de conexão. Verifique sua internet e tente novamente.'),
  ).toBeInTheDocument()
})

test('requires both fields, toggles password visibility and explains the unavailable recovery flows', async () => {
  const user = userEvent.setup()
  renderWithProviders(<LoginForm />)

  await user.click(screen.getByRole('button', { name: 'Entrar no sistema' }))
  expect(await screen.findByText('Informe seu usuário ou e-mail.')).toBeInTheDocument()
  expect(screen.getByText('Informe sua senha.')).toBeInTheDocument()

  const passwordInput = screen.getByLabelText('Senha')
  expect(passwordInput).toHaveAttribute('type', 'password')
  await user.click(screen.getByRole('button', { name: 'Mostrar senha' }))
  expect(passwordInput).toHaveAttribute('type', 'text')
  await user.click(screen.getByRole('button', { name: 'Ocultar senha' }))
  expect(passwordInput).toHaveAttribute('type', 'password')

  // "Esqueci a senha" avisa que não está disponível em vez de falhar em silêncio.
  const notice = /recuperação de senha por conta própria ainda não está disponível/i
  expect(screen.queryByText(notice)).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Esqueci a senha' }))
  expect(screen.getByText(notice)).toBeInTheDocument()

  // Ajuda do administrador é um link real, não texto morto.
  expect(screen.getByRole('link', { name: 'Fale com o administrador.' })).toHaveAttribute(
    'href',
    expect.stringMatching(/^mailto:/),
  )
})
