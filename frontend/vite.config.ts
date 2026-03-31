import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/auth': {
        target: 'http://localhost:8000',
        rewrite: (path: string) => path.replace(/^\/api\/auth/, ''),
      },
      '/api/lobby': {
        target: 'http://localhost:8001',
        rewrite: (path: string) => path.replace(/^\/api\/lobby/, ''),
      },
      '/api/chess': {
        target: 'http://localhost:8002',
        rewrite: (path: string) => path.replace(/^\/api\/chess/, ''),
      },
    },
  },
})
