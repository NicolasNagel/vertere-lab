import { expect, test } from 'vitest'

import { ApiError } from '../shared/api/errors'
import { shouldRetry } from './providers'

// Achado em teste manual: sem essa regra, uma query que falha com 403 fica
// presa em `status: 'pending'` esperando a segunda tentativa nunca resolver
// (retry pausado pelo QueryObserver), e a tela nunca chega a mostrar a
// mensagem de "sem permissão" — ver .claude/rules/05-frontend-web-mobile.md, "401 e 403
// tratados como casos diferentes na UI" pressupõe que o estado de erro
// realmente é alcançado.
test('never retries a 4xx client error (permission/validation/not-found)', () => {
  expect(shouldRetry(0, new ApiError(403, 'FORBIDDEN', 'sem permissão'))).toBe(false)
  expect(shouldRetry(0, new ApiError(404, 'NOT_FOUND', 'não encontrado'))).toBe(false)
  expect(shouldRetry(0, new ApiError(422, 'VALIDATION_ERROR', 'inválido'))).toBe(false)
})

test('retries a 5xx server error once', () => {
  expect(shouldRetry(0, new ApiError(500, 'INTERNAL_ERROR', 'erro interno'))).toBe(true)
  expect(shouldRetry(1, new ApiError(500, 'INTERNAL_ERROR', 'erro interno'))).toBe(false)
})

test('retries a plain network failure once', () => {
  expect(shouldRetry(0, new TypeError('Failed to fetch'))).toBe(true)
  expect(shouldRetry(1, new TypeError('Failed to fetch'))).toBe(false)
})
