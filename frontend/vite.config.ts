import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
const proxy = {
  '/api': { target: 'http://127.0.0.1:8000' },
  '/health': { target: 'http://127.0.0.1:8000' },
  '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
}
export default defineConfig({
  plugins: [react()],
  // The deferred 3D scene includes its WebGL renderer and is intentionally
  // loaded separately from the main dashboard bundle.
  build: { chunkSizeWarningLimit: 1000 },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy },
})

