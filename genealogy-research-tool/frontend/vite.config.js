import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',  // Allow external access
    strictPort: true,
    allowedHosts: ['scrim.local.mk-labs.cloud', 'localhost'],
  },
  preview: {
    port: 5173,
    host: '0.0.0.0',
  },
})
