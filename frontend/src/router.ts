/**
 * Re-export of the central router table.
 *
 * The actual route definitions live in `./router/index.ts`. This file is
 * kept as a thin pass-through so existing imports (`from './router'`) keep
 * working while the project transitions to the Feature-Sliced layout.
 */
export { default, router, ROUTES } from './router/index'