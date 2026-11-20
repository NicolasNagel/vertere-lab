import { renderHook } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { useSubmitGuard } from './use-submit-guard'

test('ignores a second submit until the first one releases the guard', () => {
  const { result } = renderHook(() => useSubmitGuard())
  const submit = vi.fn()

  result.current(submit)
  result.current(submit)
  expect(submit).toHaveBeenCalledTimes(1)

  const release = submit.mock.calls[0]?.[0] as () => void
  release()
  result.current(submit)
  expect(submit).toHaveBeenCalledTimes(2)
})
