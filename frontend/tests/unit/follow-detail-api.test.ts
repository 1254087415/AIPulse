/**
 * followDetail API client — db id + uid alias fallback (Phase 8 R2#2).
 *
 * The URL contract allows two shapes:
 *   /api/followed-up/{db_id}/overview           (canonical)
 *   /api/followed-up/by-uid/{platform}/{uid}/overview  (alias)
 *
 * fetchOverview must transparently resolve either into a FollowedUpOverview:
 *   - DB id resolves on first try.
 *   - Raw platform uid (B站 mid) hits the canonical endpoint with 404,
 *     which triggers a fallback to /by-uid/bilibili/{uid}/overview.
 *   - Any non-404 error must propagate (no silent swallowing).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/lib/apiFetch'
import { fetchOverview } from '../../src/api/followDetail'

const fetchMock = vi.fn()

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('fetchOverview (R2#2 dual-key lookup)', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    fetchMock.mockReset()
    globalThis.fetch = fetchMock as unknown as typeof fetch
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
  })

  const overviewData = {
    id: 'fup_abc',
    platform: 'bilibili',
    uid: '1567748478',
    display_name: '跟李沐学AI',
    profile_url: 'https://space.bilibili.com/1567748478',
    health: {
      health: 'healthy',
      last_checked_at: null,
      last_error: null,
      failed_at: null,
      is_active: true,
      fetch_interval_minutes: 30,
      status: 'active',
    },
    config: {},
    recent_jobs: [],
    recent_learning_events: [],
    recent_collections: [],
  }

  const overviewResponse = { success: true, data: overviewData }

  it('returns the canonical db-id result on the first call (no fallback)', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(overviewResponse, 200))

    const data = await fetchOverview('fup_abc')

    expect(data).toEqual(overviewData)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url] = fetchMock.mock.calls[0] as [string]
    expect(url.endsWith('/api/followed-up/fup_abc/overview')).toBe(true)
  })

  it('falls back to /by-uid/bilibili/{uid}/overview when the canonical call 404s', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: 'Not Found' }, 404))
      .mockResolvedValueOnce(jsonResponse(overviewResponse, 200))

    const data = await fetchOverview('1567748478')

    expect(data).toEqual(overviewData)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const [firstUrl] = fetchMock.mock.calls[0] as [string]
    const [secondUrl] = fetchMock.mock.calls[1] as [string]
    expect(firstUrl.endsWith('/api/followed-up/1567748478/overview')).toBe(true)
    expect(secondUrl.endsWith('/api/followed-up/by-uid/bilibili/1567748478/overview')).toBe(true)
  })

  it('throws the original error when the canonical call returns a non-404 status', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'Internal error' }, 500))

    await expect(fetchOverview('1567748478')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('throws when both canonical and alias attempts 404', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: 'Not Found' }, 404))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Not Found' }, 404))

    await expect(fetchOverview('1567748478')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
