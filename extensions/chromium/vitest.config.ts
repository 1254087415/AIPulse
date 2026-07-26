import { defineConfig } from 'vitest/config';

export default defineConfig({
  define: {
    __E2E__: 'false',
  },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.ts', 'tests/unit/**/*.test.tsx'],
  },
});
