/**
 * TasksView — must not throw under a browser environment (Phase 8 R2#3).
 *
 * `/tasks` is a legacy Tauri-only window: its `invoke()` calls hit the
 * Rust backend directly through `@tauri-apps/api/core`. Under vite dev
 * (browser) `window.__TAURI_INTERNALS__` is undefined, so the module's
 * dynamic `transformCallback()` path crashes on every load. The view
 * must instead detect the missing Tauri environment and render an
 * informative fallback that links back to the v0.3 dashboard.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import TasksView from '../../src/views/TasksView.vue'

const invokeMock = vi.fn()
const listenMock = vi.fn()

vi.mock('@tauri-apps/api/core', () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}))
vi.mock('@tauri-apps/api/event', () => ({
  listen: (...args: unknown[]) => listenMock(...args),
}))

describe('TasksView — browser environment (R2#3)', () => {
  beforeEach(() => {
    invokeMock.mockReset()
    listenMock.mockReset()
    listenMock.mockResolvedValue(() => undefined)
    // Mimic a vite dev server: the Tauri internals are NOT exposed.
    delete (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__
  })

  it('does not call invoke() or listen() when the Tauri environment is missing', async () => {
    const wrapper = mount(TasksView, {
      global: {
        plugins: [
          createRouter({
            history: createMemoryHistory(),
            routes: [{ path: '/tasks', component: TasksView }],
          }),
        ],
      },
    })
    await flushPromises()

    expect(invokeMock).not.toHaveBeenCalled()
    expect(listenMock).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="tasks-browser-fallback"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('桌面端')
    wrapper.unmount()
  })

  it('shows a link back to the dashboard', async () => {
    const wrapper = mount(TasksView, {
      global: {
        plugins: [
          createRouter({
            history: createMemoryHistory(),
            routes: [
              { path: '/tasks', component: TasksView },
              { path: '/dashboard', component: { template: '<div data-testid="d" />' } },
            ],
          }),
        ],
      },
    })
    await flushPromises()
    const link = wrapper.find('[data-testid="tasks-back-to-dashboard"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('/dashboard')
    wrapper.unmount()
  })
})
