import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// `test.globals` não está habilitado (vite.config.ts), então o cleanup
// automático do Testing Library entre testes precisa ser registrado aqui.
afterEach(() => {
  cleanup()
})
