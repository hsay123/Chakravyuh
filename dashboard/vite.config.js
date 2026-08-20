import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/incidents': 'http://localhost:8000',
      '/audit-log': 'http://localhost:8000',
      '/stream': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
