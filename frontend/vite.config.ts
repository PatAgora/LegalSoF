import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    allowedHosts: [
      '5173-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai',
      '5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai',
      'localhost',
      '.sandbox.novita.ai',
    ],
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
