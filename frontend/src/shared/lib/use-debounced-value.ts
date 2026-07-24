import { useEffect, useState } from 'react'

/** Delays reflecting `value` until it stops changing for `delayMs` — used to
 * avoid firing a request on every keystroke (rule: .claude/rules/frontend.md,
 * "debounce em busca sem atrasar a seleção"). */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timeoutId = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timeoutId)
  }, [value, delayMs])

  return debounced
}
