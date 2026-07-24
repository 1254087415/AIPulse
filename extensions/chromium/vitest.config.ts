import { defineConfig } from 'vitest/config';

export default defineConfig({
  defineEnv: {
    VITEST: 'true',
  },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.ts', 'tests/unit/**/*.test.tsx'],
  },
});
