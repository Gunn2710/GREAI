import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The FastAPI backend runs on :8000; proxying keeps the browser same-origin in dev.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // GRE_API_TARGET lets a second dev stack point at another backend port.
      '/api': process.env.GRE_API_TARGET ?? 'http://localhost:8000',
    },
  },
})
