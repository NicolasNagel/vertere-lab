/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Same-origin do ponto de vista do navegador — o cookie HttpOnly de
    // sessão só funciona assim em dev (backend roda em outra porta).
    proxy: {
      '/api': {
        // Porta 8000 tem um processo travado nesta máquina servindo código
        // antigo (não responde a restart nem kill) — apontando para 8002
        // até o ambiente ser limpo. Reverter para 8000 quando resolvido.
        target: 'http://localhost:8321',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/test/setup.ts'],
  },
})
