/**
 * API client barrel — single import surface for backend integrations.
 *
 * Consumers can import any client from `../api` (e.g. `import { listFollowed }
 * from '../api'`). Keeping a single index keeps refactors painless when we
 * split or rename modules.
 */

export * from './followedUp'