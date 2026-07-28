import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
//
// `appType: 'spa'` (the default) makes the dev server fall back to
// `index.html` for any unknown route, which is what createWebHistory() needs.
// We keep `base: '/'` so that absolute paths in the HTML resolve correctly
// under HTML5 history mode.
export default defineConfig({
  plugins: [vue()],
  base: '/',
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    host: 'localhost',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:18000',
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
  },
  envPrefix: ['VITE_', 'TAURI_'],
})
