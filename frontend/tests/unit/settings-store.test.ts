import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

describe('settings-store API token bootstrap', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.resetModules()
  })

  afterEach(() => {
    window.localStorage.clear()
    vi.unstubAllEnvs()
  })

  it('uses the backend token injected from the root environment when storage is empty', async () => {
    vi.stubEnv('AIPULSE_API_TOKEN', 'env-token')
    const { getApiToken } = await import('../../src/lib/settings-store')

    expect(getApiToken()).toBe('env-token')
  })

  it('prefers a user-saved token over the injected environment token', async () => {
    vi.stubEnv('AIPULSE_API_TOKEN', 'env-token')
    window.localStorage.setItem('aipulse.apiToken', 'saved-token')
    const { getApiToken } = await import('../../src/lib/settings-store')

    expect(getApiToken()).toBe('saved-token')
  })
})
