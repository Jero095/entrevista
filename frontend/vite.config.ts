import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// En desarrollo (npm run dev) las llamadas a /api y /health se reenvían a la API.
// En Docker ese papel lo cumple nginx (ver nginx.conf), así el navegador siempre
// habla con el mismo origen y no hace falta CORS.
const apiTarget = process.env.API_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': apiTarget,
      '/health': apiTarget,
    },
  },
})
