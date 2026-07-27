import { describe, expect, it, vi } from 'vitest'
import {
  enqueueSummary,
  getSummaryJob,
  listSummaryJobs,
  subscribeSummaryEvents,
} from '../summary'

const jsonResponse = (data: unknown, status = 200) =>
  new Response(JSON.stringify({ success: true, data }), { status })

describe('summary api client', () => {
  it('enqueueSummary posts to /summary/{video_id} and unwraps data', async () => {
    const spy = vi.fn(async () => jsonResponse({ job_id: 'j1', status: 'queued', reused: false, video_id: 'BV1' }))
    vi.stubGlobal('fetch', spy)

    const result = await enqueueSummary('BV1xxx')

    expect(result).toEqual({ job_id: 'j1', status: 'queued', reused: false, video_id: 'BV1' })
    expect(spy).toHaveBeenCalledWith(
      '/api/summary/BV1xxx',
      expect.objectContaining({ method: 'POST' }),
    )
    vi.unstubAllGlobals()
  })

  it('getSummaryJob fetches /summary/job/{id}', async () => {
    const spy = vi.fn(async () => jsonResponse({ id: 'j1', video_id: 'BV1', status: 'running' }))
    vi.stubGlobal('fetch', spy)

    const job = await getSummaryJob('j1')

    expect(job.video_id).toBe('BV1')
    expect(spy).toHaveBeenCalledWith(
      '/api/summary/job/j1',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    vi.unstubAllGlobals()
  })

  it('listSummaryJobs fetches /summary/jobs and unwraps data array', async () => {
    const spy = vi.fn(async () => jsonResponse([{ id: 'j1' }, { id: 'j2' }]))
    vi.stubGlobal('fetch', spy)

    const jobs = await listSummaryJobs()

    expect(jobs).toHaveLength(2)
    expect(spy).toHaveBeenCalledWith(
      '/api/summary/jobs',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    vi.unstubAllGlobals()
  })

  it('subscribeSummaryEvents returns a disposer that closes the EventSource', () => {
    const closed = vi.fn()
    class FakeEventSource {
      static instances: FakeEventSource[] = []
      url: string
      onmessage: ((event: MessageEvent) => void) | null = null
      onerror: ((event: Event) => void) | null = null
      close: () => void = closed
      constructor(url: string) {
        this.url = url
        FakeEventSource.instances.push(this)
      }
    }
    ;(globalThis as unknown as { EventSource: unknown }).EventSource = FakeEventSource

    const handle = subscribeSummaryEvents('j1', { onEvent: () => {} })

    expect(FakeEventSource.instances).toHaveLength(1)
    expect(FakeEventSource.instances[0]!.url).toBe('/api/summary/events/j1')

    handle.close()

    expect(closed).toHaveBeenCalled()
  })

  it('subscribeSummaryEvents dispatches parsed event to onEvent', () => {
    const captured: Array<{
      onmessage: ((event: MessageEvent) => void) | null
      onerror: ((event: Event) => void) | null
      close: () => void
    }> = []
    class FakeEventSource {
      url: string
      onmessage: ((event: MessageEvent) => void) | null = null
      onerror: ((event: Event) => void) | null = null
      close: () => void = vi.fn()
      constructor(url: string) {
        this.url = url
        captured.push(this)
      }
    }
    ;(globalThis as unknown as { EventSource: unknown }).EventSource = FakeEventSource

    const onEvent = vi.fn()
    subscribeSummaryEvents('j1', { onEvent })

    expect(captured).toHaveLength(1)
    captured[0]!.onmessage?.(
      new MessageEvent('message', { data: JSON.stringify({ type: 'started', job_id: 'j1' }) }),
    )

    expect(onEvent).toHaveBeenCalledWith({ type: 'started', job_id: 'j1' })
  })
})