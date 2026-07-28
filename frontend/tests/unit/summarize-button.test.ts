/**
 * D7 SummarizeButton — spec §6.13.
 *
 * Coverage (verifier expects 9/9):
 *  - mounts in `idle` state when `hasSummary` is false
 *  - mounts in `done` state when `hasSummary` is true (the URL has a note)
 *  - click in `idle` state → POSTs `/api/summary/{bvid}` and enters `pending`
 *    → `queued` on success
 *  - click in `done` state triggers a navigation to
 *    `obsidian://open?path=<encoded obsidianPath>`
 *  - listens for five SSE event names on the agent task stream:
 *      agent.queue.updated, agent.task.{bvid}.started,
 *      agent.task.{bvid}.step, agent.task.{bvid}.done,
 *      agent.task.{bvid}.failed
 *  - on `started` event the status becomes `running`
 *  - on `step` event the title/aria reflects the latest step
 *  - on `done` event the status becomes `done`
 *  - on `failed` event the status becomes `failed` and the error message
 *    surface is populated, plus the component unmounts to clean up the
 *    EventSource subscription.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'

type Listener = (event: { data: string }) => void

// vi.hoisted runs before vi.mock hoisting, so the MockEventSource global
// is in place by the time `subscribeSse` resolves `EventSource` at runtime.
const { MockEventSource } = vi.hoisted(() => {
  return {
    MockEventSource: class {
      static instances: MockEventSource[] = []
      url: string
      readyState = 0
      listeners: Array<{ name: string; fn: Listener }> = []
      constructor(url: string) {
        this.url = url
        MockEventSource.instances.push(this)
      }
      addEventListener(name: string, fn: Listener) {
        this.listeners.push({ name, fn })
      }
      removeEventListener(name: string, fn: Listener) {
        this.listeners = this.listeners.filter(
          (l) => !(l.name === name && l.fn === fn),
        )
      }
      close() {
        this.readyState = 2
      }
      emit(name: string, data: unknown) {
        for (const l of this.listeners) {
          if (l.name === name) {
            try {
              l.fn({ data: JSON.stringify(data) })
            } catch {
              /* ignore */
            }
          }
        }
      }
      hasListener(name: string): boolean {
        return this.listeners.some((l) => l.name === name)
      }
    },
  }
})

// Expose globally so `subscribeSse` resolves it at subscription time.
;(globalThis as unknown as { EventSource: unknown }).EventSource = MockEventSource

import SummarizeButton from '../../src/components/buttons/SummarizeButton.vue'

// ---- mock agentApi --------------------------------------------------------

vi.mock('../../src/api/agent', () => ({
  agentApi: {
    enqueueProcess: (...args: unknown[]) =>
      (globalThis as unknown as { enqueueSpy: (a: unknown) => unknown })
        .enqueueSpy(...args),
  },
}))

;(globalThis as unknown as { enqueueSpy: ReturnType<typeof vi.fn> }).enqueueSpy =
  vi.fn()

// ---- helpers --------------------------------------------------------------

const mountBtn = (props: Record<string, unknown> = {}) =>
  mount(SummarizeButton, {
    props: { bvid: 'BV1TEST', ...props },
    attachTo: document.body,
  })

const cleanupListeners = () => {
  MockEventSource.instances.forEach((s) => s.close())
  MockEventSource.instances = []
}

const originalLocation = window.location

beforeEach(() => {
  MockEventSource.instances = []
  ;(globalThis as unknown as { enqueueSpy: ReturnType<typeof vi.fn> }).enqueueSpy =
    vi.fn().mockResolvedValue({ job_id: 'job-1', queue_position: 2 })
})

const enqueueSpy = () =>
  (globalThis as unknown as { enqueueSpy: ReturnType<typeof vi.fn> }).enqueueSpy

afterEach(() => {
  cleanupListeners()
  vi.restoreAllMocks()
  if (window.location !== originalLocation) {
    Object.defineProperty(window, 'location', { configurable: true, value: originalLocation })
  }
})

// ----------------------------------------------------------------------------

describe('D7 SummarizeButton — mount state (spec §6.13)', () => {
  it('mounts in idle when hasSummary is false', () => {
    const w = mountBtn()
    const btn = w.find('button')
    expect(btn.classes().some((c) => c.includes('summarize-btn--idle'))).toBe(true)
    expect(btn.text()).toMatch(/总结/i)
    w.unmount()
  })

  it('mounts in done when hasSummary is true', () => {
    const w = mountBtn({ hasSummary: true, obsidianPath: 'a/b/note.md' })
    const btn = w.find('button')
    expect(btn.classes().some((c) => c.includes('summarize-btn--done'))).toBe(true)
    expect(btn.text()).toMatch(/查看总结|✓/)
    w.unmount()
  })
})

describe('D7 SummarizeButton — click handler', () => {
  it('clicking in idle posts to enqueueProcess({bvid}) and enters queued', async () => {
    const w = mountBtn()
    const btn = w.find('button')
    await btn.trigger('click')
    expect(enqueueSpy()).toHaveBeenCalledWith({ bvid: 'BV1TEST' })
    await flushPromises()
    await nextTick()
    const after = w.find('button')
    expect(
      after.classes().some((c) => c.includes('summarize-btn--queued')),
    ).toBe(true)
    expect(after.attributes('disabled')).toBeDefined()
    w.unmount()
  })

  it('clicking in done navigates to obsidian://open?path=<encoded>', async () => {
    const writes: string[] = []
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...originalLocation,
        set href(v: string) {
          writes.push(v)
        },
        get href() {
          return ''
        },
        assign: (v: string) => writes.push(v),
        replace: (v: string) => writes.push(v),
      },
    })
    const w = mountBtn({ hasSummary: true, obsidianPath: 'vault/笔记 note.md' })
    await w.find('button').trigger('click')
    await flushPromises()
    expect(
      writes.some((v) => v.startsWith('obsidian://open?path=')),
    ).toBe(true)
    const target = writes.find((v) => v.startsWith('obsidian://open?path='))!
    expect(target).toContain(encodeURIComponent('vault/笔记 note.md'))
    w.unmount()
  })
})

describe('D7 SummarizeButton — SSE 5 event subscriptions', () => {
  it('subscribes to agent.queue.updated + 4 task-scoped events on mount', () => {
    mountBtn()
    expect(MockEventSource.instances.length).toBe(1)
    const src = MockEventSource.instances[0]
    const expected = [
      'agent.queue.updated',
      'agent.task.BV1TEST.started',
      'agent.task.BV1TEST.step',
      'agent.task.BV1TEST.done',
      'agent.task.BV1TEST.failed',
    ]
    for (const name of expected) {
      expect(src.hasListener(name), `missing listener for ${name}`).toBe(true)
    }
  })

  it('started event flips status to running', async () => {
    const w = mountBtn()
    // trigger queued first to make running a meaningful transition
    await w.find('button').trigger('click')
    await flushPromises()
    MockEventSource.instances[0].emit('agent.task.BV1TEST.started', { job_id: 'job-1' })
    await flushPromises()
    const btn = w.find('button')
    expect(btn.classes().some((c) => c.includes('summarize-btn--running'))).toBe(true)
    expect(btn.attributes('aria-busy')).toBe('true')
    w.unmount()
  })

  it('step event reflects data.step in button surface', async () => {
    const w = mountBtn()
    MockEventSource.instances[0].emit('agent.task.BV1TEST.step', {
      job_id: 'job-1',
      step: 'fetch_transcript',
    })
    await flushPromises()
    const btn = w.find('button')
    const surface = btn.attributes('title') ?? btn.text()
    expect(surface).toMatch(/fetch_transcript/)
    w.unmount()
  })

  it('done event flips status to done', async () => {
    const w = mountBtn()
    MockEventSource.instances[0].emit('agent.task.BV1TEST.done', {
      job_id: 'job-1',
      note_path: 'a/b/done.md',
    })
    await flushPromises()
    const btn = w.find('button')
    expect(btn.classes().some((c) => c.includes('summarize-btn--done'))).toBe(true)
    w.unmount()
  })

  it('failed event flips status to failed and surfaces errorMessage', async () => {
    const w = mountBtn()
    MockEventSource.instances[0].emit('agent.task.BV1TEST.failed', {
      job_id: 'job-1',
      error: 'network timeout',
    })
    await flushPromises()
    const btn = w.find('button')
    expect(btn.classes().some((c) => c.includes('summarize-btn--failed'))).toBe(true)
    const surface = btn.attributes('title') ?? btn.text()
    expect(surface).toMatch(/network timeout/)
    w.unmount()
  })

  it('unmount closes the SSE connection', () => {
    const w = mountBtn()
    const src = MockEventSource.instances[0]
    expect(src.readyState).toBe(0)
    w.unmount()
    expect(src.readyState).toBe(2)
  })
})
