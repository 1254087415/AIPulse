import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import webExtension from 'vite-plugin-web-extension';

export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    webExtension({
      manifest: 'manifest.json',
      additionalInputs: ['src/content.ts', 'src/context.ts', 'src/background.ts'],
    }),
  ],
  define: {
    __E2E__: mode === 'e2e' ? 'true' : 'false',
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
}));
