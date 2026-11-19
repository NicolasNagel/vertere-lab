import { useCallback, useRef } from 'react'

/**
 * Drops a second submit fired before React re-renders with the mutation's `isPending` (a fast
 * double click lands two submit events on the same render, so the disabled button is too late).
 * The caller releases the guard from the mutation's `onSettled`.
 */
export function useSubmitGuard() {
  const inFlight = useRef(false)
  return useCallback((submit: (release: () => void) => void) => {
    if (inFlight.current) return
    inFlight.current = true
    submit(() => {
      inFlight.current = false
    })
  }, [])
}
