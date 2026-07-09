import { mergeConfig } from 'vite'
import { defineConfig } from 'vitest/config'
import baseConfig from './vite.config'

export default mergeConfig(baseConfig, defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
  },
}))
