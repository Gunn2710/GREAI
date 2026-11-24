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
  build: {
    rollupOptions: {
      output: {
        // Libraries change far less often than the app, so they get their own
        // files: after a deploy, returning visitors only download the app's code.
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (/node_modules\/(@clerk)\//.test(id)) return 'clerk'
          if (/node_modules\/(react|react-dom|scheduler|react-router|react-router-dom|@remix-run)\//.test(id))
            return 'react'
        },
      },
    },
  },
  server: {
    proxy: {
      // GRE_API_TARGET lets a second dev stack point at another backend port.
      '/api': process.env.GRE_API_TARGET ?? 'http://localhost:8000',
    },
  },
})
