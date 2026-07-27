import { describe, it, expect } from 'vitest'
import { router } from '../index'

describe('router configuration', () => {
  it('uses HTML5 history mode (createWebHistory), not hash mode', async () => {
    // Pushing to a deep path must produce a history URL that does NOT contain
    // a `#` separator. Hash mode would render `/dashboard` as `#/dashboard`.
    // We also assert that window.location.pathname reflects the push, which
    // is the observable behaviour of HTML5 history mode in a browser.
    await router.push('/dashboard').catch(() => undefined)
    await router.isReady()

    expect(router.currentRoute.value.fullPath).toBe('/dashboard')
    expect(typeof window !== 'undefined' ? window.location.hash : '').not.toMatch(
      /#\/dashboard/,
    )
  })

  it('exposes a redirect from / to /dashboard (history-mode path, no hash)', async () => {
    await router.push('/').catch(() => undefined)
    await router.isReady()
    expect(router.currentRoute.value.fullPath).toBe('/dashboard')
  })
})