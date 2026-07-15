import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: './',
  server: {
    port: 5174,
    strictPort: true,
    host: 'localhost',
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
