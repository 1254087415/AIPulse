import { describe, it, expect, vi, beforeEach } from 'vitest'

const { getApiTokenMock, fetchMock } = vi.hoisted(() => ({
  getApiTokenMock: vi.fn(),
  fetchMock: vi.fn(),
}))

vi.mock('../../src/lib/settings-store', () => ({
  getApiToken: () => getApiTokenMock(),
}))

import { apiFetch } from '../../src/lib/apiFetch'

const TOKEN = 'super-secret-token-123'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('apiFetch', () => {
  beforeEach(() => {
    getApiTokenMock.mockReset()
    fetchMock.mockReset()
    globalThis.fetch = fetchMock as unknown as typeof fetch
  })

  it('appends Authorization Bearer header when a token is configured', async () => {
    getApiTokenMock.mockReturnValue(TOKEN)
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }))

    await apiFetch('/api/followed-up', { method: 'GET' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url.endsWith('/api/followed-up')).toBe(true)
    expect(init.method).toBe('GET')
    const headers = new Headers(init.headers)
    expect(headers.get('Authorization')).toBe(`Bearer ${TOKEN}`)
  })

  it('omits Authorization header when no token is configured (local dev)', async () => {
    getApiTokenMock.mockReturnValue('')
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }))

    await apiFetch('/api/followed-up', { method: 'GET' })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(init.headers)
    expect(headers.has('Authorization')).toBe(false)
  })

  it('merges caller-provided headers with the Bearer header', async () => {
    getApiTokenMock.mockReturnValue(TOKEN)
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }))

    await apiFetch('/api/followed-up', {
      method: 'POST',
      headers: { 'X-Trace-Id': 'abc' },
      body: JSON.stringify({ uid: 'foo' }),
    })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(init.headers)
    expect(headers.get('Authorization')).toBe(`Bearer ${TOKEN}`)
    expect(headers.get('X-Trace-Id')).toBe('abc')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('parses JSON responses and returns them', async () => {
    getApiTokenMock.mockReturnValue('')
    fetchMock.mockResolvedValue(jsonResponse({ items: [1, 2, 3] }))

    const result = await apiFetch<{ items: number[] }>('/api/followed-up', { method: 'GET' })

    expect(result).toEqual({ items: [1, 2, 3] })
  })

  it('throws ApiError with status and body on non-2xx responses', async () => {
    getApiTokenMock.mockReturnValue('')
    fetchMock.mockResolvedValue(jsonResponse({ message: 'duplicate uid' }, 409))

    await expect(apiFetch('/api/followed-up', { method: 'POST' })).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      body: { message: 'duplicate uid' },
    })
  })

  it('uses relative base URL so Tauri webview can reach the embedded FastAPI', async () => {
    getApiTokenMock.mockReturnValue('')
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }))

    await apiFetch('/api/followed-up', { method: 'GET' })

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit]
    // Path component must end with /api/followed-up; in the browser the URL is
    // resolved against the document origin, in jsdom it gets an absolute form.
    expect(url.endsWith('/api/followed-up')).toBe(true)
  })

  it('honors skipAuth to bypass the Authorization header even when configured', async () => {
    getApiTokenMock.mockReturnValue(TOKEN)
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }))

    await apiFetch('/api/health', { method: 'GET', skipAuth: true })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(init.headers)
    expect(headers.has('Authorization')).toBe(false)
  })
})