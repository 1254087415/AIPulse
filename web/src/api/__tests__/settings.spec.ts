import { describe, expect, it, vi } from 'vitest'
import { fetchSettings, updateSettings } from '../settings'

const jsonResponse = (data: unknown, status = 200) =>
  new Response(JSON.stringify({ success: true, data }), { status })

describe('settings api client', () => {
  it('fetchSettings hits GET /settings and unwraps data', async () => {
    const spy = vi.fn(async () =>
      jsonResponse({ kimi: { kimi_api_key: '***' }, obsidian: {}, wechat: {}, feishu: {} }),
    )
    vi.stubGlobal('fetch', spy)

    const settings = await fetchSettings()

    expect(settings.kimi.kimi_api_key).toBe('***')
    expect(spy).toHaveBeenCalledWith(
      '/api/settings',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    vi.unstubAllGlobals()
  })

  it('updateSettings sends PATCH body and returns refreshed settings', async () => {
    const spy = vi.fn(async () =>
      jsonResponse({ kimi: { kimi_model: 'kimi-for-coding' }, obsidian: {}, wechat: {}, feishu: {} }),
    )
    vi.stubGlobal('fetch', spy)

    const updated = await updateSettings({ kimi_model: 'kimi-for-coding' })

    expect(updated.kimi.kimi_model).toBe('kimi-for-coding')
    expect(spy).toHaveBeenCalledWith(
      '/api/settings',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ kimi_model: 'kimi-for-coding' }),
      }),
    )
    vi.unstubAllGlobals()
  })

  it('updateSettings surfaces 400 status on invalid obsidian path', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ success: false, error: 'path not found' }), { status: 400 }),
      ),
    )

    await expect(updateSettings({ obsidian_vault_path: '/nope' })).rejects.toMatchObject({ status: 400 })
    vi.unstubAllGlobals()
  })
})