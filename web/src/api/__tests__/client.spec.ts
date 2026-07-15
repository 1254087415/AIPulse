import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { API_BASE, ApiError, apiFetch } from '../client'

describe('apiFetch', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => {
        return new Response(JSON.stringify({ success: true, data: {} }), { status: 200 })
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns parsed JSON on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ data: 'ok' }), { status: 200 })),
    )

    const result = await apiFetch<{ data: string }>('/test')

    expect(result).toEqual({ data: 'ok' })
    expect(fetch).toHaveBeenCalledWith(`${API_BASE}/test`, expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('prepends API_BASE to the path', async () => {
    await apiFetch('/test')

    expect(fetch).toHaveBeenCalledWith('/api/test', expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('passes init options to fetch with an abort signal', async () => {
    await apiFetch('/test', { method: 'POST', body: JSON.stringify({ key: 'value' }) })

    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/test`,
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ key: 'value' }), signal: expect.any(AbortSignal) }),
    )
  })

  it('throws ApiError when response is not ok', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('Not Found', { status: 404, statusText: 'Not Found' })),
    )

    await expect(apiFetch('/missing')).rejects.toThrow('请求失败，请稍后重试')
    await expect(apiFetch('/missing')).rejects.toSatisfy((error: unknown) => {
      if (!(error instanceof ApiError)) return false
      return error.status === 404
    })
  })

  it('throws ApiError when body success is false', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ success: false, error: 'validation failed' }), { status: 200 }),
      ),
    )

    await expect(apiFetch('/submit')).rejects.toThrow('validation failed')
    await expect(apiFetch('/submit')).rejects.toSatisfy((error: unknown) => {
      if (!(error instanceof ApiError)) return false
      return error.status === 200
    })
  })

  it('throws generic ApiError when body success is false but error is missing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ success: false }), { status: 200 })),
    )

    await expect(apiFetch('/submit')).rejects.toThrow('请求失败，请稍后重试')
  })

  it('throws when response body is not valid JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('not json', { status: 200 })))

    await expect(apiFetch('/broken')).rejects.toThrow(SyntaxError)
  })

  it('throws a friendly error when the request times out', async () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        return new Promise<Response>((_resolve, reject) => {
          const signal = init?.signal
          if (!signal) return
          signal.addEventListener('abort', () => {
            const error = new Error('The operation was aborted')
            error.name = 'AbortError'
            reject(error)
          })
        })
      }),
    )

    const promise = apiFetch('/slow')
    vi.advanceTimersByTime(10001)

    await expect(promise).rejects.toThrow('请求超时，请检查后端服务')
    vi.useRealTimers()
  })
})

describe('ApiError', () => {
  it('exposes message and status', () => {
    const error = new ApiError('bad request', 400)

    expect(error.message).toBe('bad request')
    expect(error.status).toBe(400)
    expect(error).toBeInstanceOf(Error)
  })
})
