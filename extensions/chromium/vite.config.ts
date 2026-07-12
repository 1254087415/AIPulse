import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import webExtension from 'vite-plugin-web-extension';

export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    webExtension({
      manifest: 'manifest.json',
      additionalInputs: ['src/content.ts', 'src/context.ts', 'src/background.ts'],
      skipManifestValidation: true,
      // ^ vite-plugin-web-extension fetches the manifest schema from SchemaStore on
      // every build; that endpoint rate-limits (429) and breaks CI. The local
      // manifest.json is still emitted and loaded by the browser.
      transformManifest: (manifest) => {
        // The E2E mock server on localhost:3456 must stay out of the production
        // manifest; inject it only for e2e builds.
        if (mode === 'e2e') {
          const mockOrigin = 'http://localhost:3456/*';
          manifest.host_permissions = [...(manifest.host_permissions ?? []), mockOrigin];
          manifest.content_scripts = (manifest.content_scripts ?? []).map((script) => ({
            ...script,
            matches: [...(script.matches ?? []), mockOrigin],
          }));
        }
        return manifest;
      },
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
