import { afterEach, expect, test, vi } from 'vitest'

import type { ApiError } from './errors'
import { apiRequest } from './http-client'

afterEach(() => vi.restoreAllMocks())

test('sends cookies and serializes JSON consistently', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )

  await expect(apiRequest('/example', { method: 'POST', body: { value: 1 } })).resolves.toEqual({
    ok: true,
  })
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/v1/example',
    expect.objectContaining({ credentials: 'include', body: JSON.stringify({ value: 1 }) }),
  )
})

test.each([401, 403])('preserves authorization status %s as ApiError', async (status) => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ error: { code: 'ACCESS_DENIED', message: 'Negado.' } }), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )

  await expect(apiRequest('/protected')).rejects.toMatchObject({
    status,
    code: 'ACCESS_DENIED',
  } satisfies Partial<ApiError>)
})
