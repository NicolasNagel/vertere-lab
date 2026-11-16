import '@testing-library/jest-dom/vitest'

import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// `test.globals` não está habilitado (vite.config.ts), então o cleanup
// automático do Testing Library entre testes precisa ser registrado aqui.
afterEach(() => {
  cleanup()
})

// 1 s (padrão) é curto quando 30 arquivos rodam em paralelo: as buscas `findBy*` falhavam
// de forma intermitente em telas não relacionadas. O tempo só vale para quem espera algo aparecer.
configure({ asyncUtilTimeout: 5000 })
