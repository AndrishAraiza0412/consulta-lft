import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const API = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/ask': API, '/health': API },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test-setup.ts',
  },
})
