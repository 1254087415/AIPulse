import { describe, it, expect, vi, beforeEach } from 'vitest'

const { apiFetchMock } = vi.hoisted(() => ({
  apiFetchMock: vi.fn(),
}))

vi.mock('../../src/lib/apiFetch', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  ApiError: class ApiError extends Error {
    status: number
    body: unknown
    constructor(status: number, body: unknown, message: string) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.body = body
    }
  },
}))

import {
  listFollowed,
  createFollowed,
  getFollowed,
  updateFollowed,
  deleteFollowed,
  validateFollowed,
  syncFollowed,
  type FollowedUp,
  type FollowedUpCreate,
} from '../../src/api/followedUp'

const sampleFollowed: FollowedUp = {
  id: 'fu_123',
  platform: 'bilibili',
  uid: '1567748478',
  display_name: '李沐',
  profile_url: 'https://space.bilibili.com/1567748478',
  collector_strategy: 'uapi',
  last_cursor_id: null,
  fetch_interval_minutes: 30,
  is_active: true,
  status: 'active',
  health: 'healthy',
  last_checked_at: '2026-07-25T08:00:00Z',
  last_error: null,
  failed_at: null,
  created_at: '2026-07-25T07:00:00Z',
  updated_at: '2026-07-25T08:00:00Z',
  deleted_at: null,
}

describe('followedUp API client', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('listFollowed calls GET /api/followed-up and unwraps the items array', async () => {
    apiFetchMock.mockResolvedValue({ items: [sampleFollowed], total: 1 })

    const items = await listFollowed()

    expect(apiFetchMock).toHaveBeenCalledWith('/api/followed-up', { method: 'GET' })
    expect(items).toEqual([sampleFollowed])
  })

  it('listFollowed accepts includeDeleted flag', async () => {
    apiFetchMock.mockResolvedValue({ items: [], total: 0 })

    await listFollowed({ includeDeleted: true })

    const [url, init] = apiFetchMock.mock.calls[0] as [string, RequestInit & { query?: Record<string, string> }]
    expect(url.startsWith('/api/followed-up')).toBe(true)
    expect(init.method).toBe('GET')
    expect((init as { query?: Record<string, string> }).query).toEqual({
      include_deleted: 'true',
    })
  })

  it('createFollowed posts the payload to /api/followed-up', async () => {
    apiFetchMock.mockResolvedValue(sampleFollowed)

    const payload: FollowedUpCreate = { platform: 'bilibili', uid: '1567748478' }
    const result = await createFollowed(payload)

    expect(apiFetchMock).toHaveBeenCalledWith('/api/followed-up', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    expect(result).toEqual(sampleFollowed)
  })

  it('getFollowed fetches by id', async () => {
    apiFetchMock.mockResolvedValue(sampleFollowed)

    const result = await getFollowed('fu_123')

    expect(apiFetchMock).toHaveBeenCalledWith('/api/followed-up/fu_123', { method: 'GET' })
    expect(result).toEqual(sampleFollowed)
  })

  it('updateFollowed patches only the provided fields', async () => {
    apiFetchMock.mockResolvedValue({ ...sampleFollowed, is_active: false })

    await updateFollowed('fu_123', { is_active: false })

    expect(apiFetchMock).toHaveBeenCalledWith('/api/followed-up/fu_123', {
      method: 'PATCH',
      body: JSON.stringify({ is_active: false }),
    })
  })

  it('deleteFollowed sends DELETE to the id-scoped resource', async () => {
    apiFetchMock.mockResolvedValue({ ok: true })

    await deleteFollowed('fu_123')

    expect(apiFetchMock).toHaveBeenCalledWith('/api/followed-up/fu_123', { method: 'DELETE' })
  })

  it('validateFollowed checks a uid+platform pair before creating', async () => {
    apiFetchMock.mockResolvedValue({ valid: true, display_name: '李沐', avatar_url: null })

    const result = await validateFollowed({ platform: 'bilibili', uid: '1567748478' })

    expect(apiFetchMock).toHaveBeenCalledWith('/api/followed-up/validate', {
      method: 'POST',
      body: JSON.stringify({ platform: 'bilibili', uid: '1567748478' }),
    })
    expect(result.valid).toBe(true)
  })

  it('syncFollowed triggers an immediate scan', async () => {
    apiFetchMock.mockResolvedValue({ queued: true, scan_id: 'scan-1' })

    const result = await syncFollowed('fu_123')

    expect(apiFetchMock).toHaveBeenCalledWith('/api/followed-up/fu_123/sync', { method: 'POST' })
    expect(result).toEqual({ queued: true, scan_id: 'scan-1' })
  })
})