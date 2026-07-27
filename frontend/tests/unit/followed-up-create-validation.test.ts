/**
 * createFollowed — fail fast on empty payloads (Phase 8 R2#4).
 *
 * The Pydantic schema rejects empty `platform` / `uid` with 422, which shows
 * up in the browser console as `Failed to load resource: 422`. The API client
 * must validate at the boundary and raise a typed error before any network
 * call is dispatched so that the server never sees a malformed body.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createFollowed } from '../../src/api/followedUp'

const fetchMock = vi.fn()

describe('createFollowed (R2#4 empty-payload guard)', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    fetchMock.mockReset()
    globalThis.fetch = fetchMock as unknown as typeof fetch
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  it('throws without calling fetch when platform is empty', async () => {
    await expect(
      createFollowed({ platform: '', uid: '12345' }),
    ).rejects.toThrow(/platform|uid/)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('throws without calling fetch when uid is empty', async () => {
    await expect(
      createFollowed({ platform: 'bilibili', uid: '' }),
    ).rejects.toThrow(/platform|uid/)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('trims whitespace before validating', async () => {
    await expect(
      createFollowed({ platform: '  ', uid: '\t' }),
    ).rejects.toThrow(/platform|uid/)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('dispatches a POST with the trimmed payload when valid', async () => {
    const successBody = {
      success: true,
      data: {
        id: 'abc',
        platform: 'bilibili',
        uid: '1567748478',
        display_name: '',
        profile_url: '',
        collector_strategy: 'uapi',
        last_cursor_id: null,
        fetch_interval_minutes: 30,
        is_active: true,
        status: 'active',
        health: 'healthy',
        last_checked_at: null,
        last_error: null,
        failed_at: null,
        created_at: '2026-07-26T00:00:00Z',
        updated_at: '2026-07-26T00:00:00Z',
        deleted_at: null,
      },
    }
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(successBody), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await createFollowed({ platform: '  bilibili  ', uid: ' 1567748478 ' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url.endsWith('/api/followed-up')).toBe(true)
    expect(init.method).toBe('POST')
    const sent = JSON.parse(String(init.body))
    expect(sent.platform).toBe('bilibili')
    expect(sent.uid).toBe('1567748478')
  })
})