import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import webExtension from 'vite-plugin-web-extension';

export default defineConfig({
  plugins: [
    react(),
    webExtension({
      manifest: 'manifest.json',
      additionalInputs: ['src/content.ts', 'src/context.ts', 'src/background.ts'],
    }),
  ],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
