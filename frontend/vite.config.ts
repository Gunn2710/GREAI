import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI backend runs on :8000; proxying keeps the browser same-origin in dev.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The repository root .env is shared with the backend. Vite only exposes
  // VITE_* values to the browser, so backend secrets stay out of the bundle.
  envDir: path.resolve(__dirname, '..'),
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    proxy: {
      // GRE_API_TARGET lets a second dev stack point at another backend port.
      '/api': process.env.GRE_API_TARGET ?? 'http://localhost:8000',
    },
  },
})
