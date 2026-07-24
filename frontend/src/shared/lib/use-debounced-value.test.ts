import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { useDebouncedValue } from './use-debounced-value'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

test('keeps the initial value until the delay elapses', () => {
  const { result } = renderHook(({ value }) => useDebouncedValue(value, 500), {
    initialProps: { value: 'a' },
  })

  expect(result.current).toBe('a')
})

test('reflects the latest value only after the delay with no further changes', () => {
  const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 500), {
    initialProps: { value: 'a' },
  })

  rerender({ value: 'ab' })
  act(() => {
    vi.advanceTimersByTime(300)
  })
  rerender({ value: 'abc' })
  act(() => {
    vi.advanceTimersByTime(300)
  })
  expect(result.current).toBe('a')

  act(() => {
    vi.advanceTimersByTime(200)
  })
  expect(result.current).toBe('abc')
})
