import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { ApiError } from '../client'
import {
  createFollowedUp,
  deleteFollowedUp,
  getFollowedUp,
  getFollowedUpOverview,
  listFollowedUps,
  syncFollowedUp,
  updateFollowedUp,
} from '../follow'

const SUCCESS = (data: unknown, status = 200) =>
  new Response(JSON.stringify({ success: true, data }), { status })

const FAILURE = (status: number, error = 'failed') =>
  new Response(JSON.stringify({ success: false, error }), { status })

describe('followedUp api client', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => SUCCESS({ data: 'ok' })),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listFollowedUps hits GET /followed-up and unwraps data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => SUCCESS([{ id: 'f1', display_name: 'X' }])),
    )

    const result = await listFollowedUps()

    expect(result).toEqual([{ id: 'f1', display_name: 'X' }])
    expect(fetch).toHaveBeenCalledWith(
      '/api/followed-up',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('createFollowedUp sends POST body', async () => {
    const spy = vi.fn(async () => SUCCESS({ id: 'new', platform: 'bilibili', uid: '123' }))
    vi.stubGlobal('fetch', spy)

    await createFollowedUp({
      platform: 'bilibili',
      uid: '123',
      profile_url: 'https://space.bilibili.com/123',
    })

    expect(spy).toHaveBeenCalledWith(
      '/api/followed-up',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          platform: 'bilibili',
          uid: '123',
          profile_url: 'https://space.bilibili.com/123',
        }),
      }),
    )
  })

  it('createFollowedUp surfaces 409 status on duplicate', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => FAILURE(409, 'duplicate')))

    await expect(
      createFollowedUp({
        platform: 'bilibili',
        uid: 'dup',
        profile_url: 'https://space.bilibili.com/dup',
      }),
    ).rejects.toSatisfy((error: unknown) => {
      return error instanceof ApiError && error.status === 409
    })
  })

  it('getFollowedUp calls GET /followed-up/{id}', async () => {
    const spy = vi.fn(async () => SUCCESS({ id: 'f42' }))
    vi.stubGlobal('fetch', spy)

    await getFollowedUp('f42')

    expect(spy).toHaveBeenCalledWith(
      '/api/followed-up/f42',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('updateFollowedUp sends PATCH body', async () => {
    const spy = vi.fn(async () => SUCCESS({ id: 'f42', display_name: 'updated' }))
    vi.stubGlobal('fetch', spy)

    await updateFollowedUp('f42', { display_name: 'updated' })

    expect(spy).toHaveBeenCalledWith(
      '/api/followed-up/f42',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ display_name: 'updated' }),
      }),
    )
  })

  it('deleteFollowedUp returns success flag from response', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => SUCCESS({ success: true })))

    await expect(deleteFollowedUp('f42')).resolves.toEqual({ success: true })
  })

  it('syncFollowedUp hits POST /followed-up/{id}/sync', async () => {
    const spy = vi.fn(async () => SUCCESS({ job_id: 'j1' }))
    vi.stubGlobal('fetch', spy)

    await syncFollowedUp('f42')

    expect(spy).toHaveBeenCalledWith(
      '/api/followed-up/f42/sync',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('getFollowedUpOverview hits /followed-up/{id}/overview', async () => {
    const spy = vi.fn(async () => SUCCESS({ followed_up: { id: 'f42' } }))
    vi.stubGlobal('fetch', spy)

    await getFollowedUpOverview('f42')

    expect(spy).toHaveBeenCalledWith(
      '/api/followed-up/f42/overview',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })
})