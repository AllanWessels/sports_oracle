/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.ts',
    // Playwright specs live in e2e/ and must not be collected by vitest.
    exclude: ['**/node_modules/**', '**/dist/**', 'e2e/**'],
  },
})
