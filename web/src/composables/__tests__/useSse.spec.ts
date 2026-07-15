import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, nextTick, type Ref } from 'vue'
import { mount } from '@vue/test-utils'
import { VueQueryPlugin } from '@tanstack/vue-query'
import { useSse } from '../useSse'
import type { SseStatus } from '../useSseHelpers'

const mockInvalidateQueries = vi.fn()

vi.mock('@tanstack/vue-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/vue-query')>('@tanstack/vue-query')
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
  }
})

class MockEventSourceInstance {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 2

  url: string
  readyState = MockEventSourceInstance.CONNECTING
  closed = false
  listeners: Record<string, Array<(event: MessageEvent) => void>> = {}
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, handler: (event: MessageEvent) => void) {
    if (!this.listeners[type]) this.listeners[type] = []
    this.listeners[type].push(handler)
  }

  removeEventListener(type: string, handler: (event: MessageEvent) => void) {
    if (!this.listeners[type]) return
    this.listeners[type] = this.listeners[type].filter((h) => h !== handler)
  }

  close() {
    this.readyState = MockEventSourceInstance.CLOSED
    this.closed = true
  }

  dispatchEvent(type: string, data?: string, keepReadyState = false) {
    const event = {
      type,
      data: data ?? '',
      target: this,
    } as unknown as MessageEvent

    if (type === 'open') {
      this.readyState = MockEventSourceInstance.OPEN
      this.onopen?.()
    }

    if (type === 'error' && !keepReadyState) {
      this.readyState = MockEventSourceInstance.CLOSED
      this.onerror?.()
    }

    const handlers = this.listeners[type] || []
    handlers.forEach((handler) => handler(event))
  }
}

const MockEventSource = Object.assign(
  vi.fn((url: string) => new MockEventSourceInstance(url)),
  {
    CONNECTING: MockEventSourceInstance.CONNECTING,
    OPEN: MockEventSourceInstance.OPEN,
    CLOSED: MockEventSourceInstance.CLOSED,
    instances: [] as MockEventSourceInstance[],
    reset() {
      MockEventSource.instances = []
      MockEventSource.mockClear()
    },
  },
)

describe('useSse', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    MockEventSource.reset()
    mockInvalidateQueries.mockClear()
    ;(globalThis as unknown as Record<string, unknown>).EventSource = MockEventSource
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function mountTestComponent() {
    let exposedStatus: Ref<SseStatus> | undefined

    const TestComponent = defineComponent({
      setup() {
        const { status } = useSse('/sse/hotspots')
        exposedStatus = status as unknown as Ref<SseStatus>
        return () => h('div')
      },
    })

    const wrapper = mount(TestComponent, { global: { plugins: [VueQueryPlugin] } })

    return { wrapper, getStatus: () => exposedStatus! }
  }

  it('creates an EventSource pointing to the combined API base and path', async () => {
    mountTestComponent()
    await nextTick()

    expect(MockEventSource).toHaveBeenCalledTimes(1)
    expect(MockEventSource.instances[0].url).toBe('/api/sse/hotspots')
  })

  it('reports connecting initially and open after the connection opens', async () => {
    const { getStatus } = mountTestComponent()
    await nextTick()

    expect(getStatus().value).toBe('connecting')

    MockEventSource.instances[0].dispatchEvent('open')
    await nextTick()

    expect(getStatus().value).toBe('open')
  })

  it('invalidates hotspot queries on hotspot.new event', async () => {
    mountTestComponent()
    await nextTick()

    MockEventSource.instances[0].dispatchEvent('hotspot.new')
    await nextTick()

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['hotspots'], exact: false })
    expect(mockInvalidateQueries).toHaveBeenCalledTimes(1)
  })

  it('invalidates hotspot list and detail queries on hotspot.updated event', async () => {
    mountTestComponent()
    await nextTick()

    MockEventSource.instances[0].dispatchEvent('hotspot.updated')
    await nextTick()

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['hotspots'], exact: false })
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['hotspot'], exact: false })
  })

  it('invalidates digest queries on digest.ready event', async () => {
    mountTestComponent()
    await nextTick()

    MockEventSource.instances[0].dispatchEvent('digest.ready')
    await nextTick()

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['digests'], exact: false })
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['digest', 'latest'], exact: false })
  })

  it('invalidates source and job queries on sync.completed event', async () => {
    mountTestComponent()
    await nextTick()

    MockEventSource.instances[0].dispatchEvent('sync.completed')
    await nextTick()

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['sources'], exact: false })
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ['jobs'], exact: false })
  })

  it('reconnects with exponential backoff when the connection drops', async () => {
    const { getStatus } = mountTestComponent()
    await nextTick()

    expect(getStatus().value).toBe('connecting')

    MockEventSource.instances[0].dispatchEvent('error')
    await nextTick()
    expect(getStatus().value).toBe('error')
    expect(MockEventSource).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(1000)
    await nextTick()
    expect(MockEventSource).toHaveBeenCalledTimes(2)
    expect(getStatus().value).toBe('connecting')

    MockEventSource.instances[1].dispatchEvent('error')
    await nextTick()
    expect(getStatus().value).toBe('error')

    vi.advanceTimersByTime(2000)
    await nextTick()
    expect(MockEventSource).toHaveBeenCalledTimes(3)
    expect(getStatus().value).toBe('connecting')

    MockEventSource.instances[2].dispatchEvent('error')
    await nextTick()
    expect(getStatus().value).toBe('error')

    vi.advanceTimersByTime(4000)
    await nextTick()
    expect(MockEventSource).toHaveBeenCalledTimes(4)
  })

  it('caps reconnection delay at 30 seconds', async () => {
    mountTestComponent()
    await nextTick()

    for (let i = 0; i < 6; i++) {
      const instance = MockEventSource.instances[i]
      instance.dispatchEvent('error')
      await nextTick()
      vi.advanceTimersByTime(Math.min(1000 * 2 ** i, 30000))
      await nextTick()
    }

    expect(MockEventSource).toHaveBeenCalledTimes(7)

    MockEventSource.instances[6].dispatchEvent('error')
    await nextTick()

    vi.advanceTimersByTime(29999)
    await nextTick()
    expect(MockEventSource).toHaveBeenCalledTimes(7)

    vi.advanceTimersByTime(1)
    await nextTick()
    expect(MockEventSource).toHaveBeenCalledTimes(8)
  })

  it('keeps status open and does not reconnect when error fires while readyState is OPEN', async () => {
    const { getStatus } = mountTestComponent()
    await nextTick()

    MockEventSource.instances[0].dispatchEvent('open')
    await nextTick()
    expect(getStatus().value).toBe('open')
    expect(MockEventSource).toHaveBeenCalledTimes(1)

    MockEventSource.instances[0].dispatchEvent('error', undefined, true)
    await nextTick()

    expect(getStatus().value).toBe('open')
    expect(MockEventSource).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('closes the EventSource and clears reconnect timers on unmount', async () => {
    const { wrapper, getStatus } = mountTestComponent()
    await nextTick()

    MockEventSource.instances[0].dispatchEvent('error')
    await nextTick()
    expect(vi.getTimerCount()).toBeGreaterThan(0)

    wrapper.unmount()
    await nextTick()

    expect(MockEventSource.instances[0].closed).toBe(true)
    expect(getStatus().value).toBe('closed')
    expect(vi.getTimerCount()).toBe(0)
  })
})
