import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The FastAPI backend defaults to port 8000. During development Vite proxies /api
// so the browser never needs CORS exceptions and relative URLs work in production.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Backend default. Override with VITE_API_PROXY only when running the
        // backend on a different host/port.
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5173,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
} as import('vite').UserConfig);
