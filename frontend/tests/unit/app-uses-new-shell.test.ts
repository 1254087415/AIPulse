/**
 * App.vue usesNewShell — every v0.3 route must use the Sidebar shell.
 *
 * Spec §6.14 / §8.1 say the v0.3 dashboard layout uses a Sidebar + main
 * two-column grid. Legacy Tauri-only windows (/input, /tasks) keep the old
 * AppHeader banner. The new AppHeader banner (legacy) renders an `<header
 * class="app-header">` element; the new shell renders an `<aside class="sidebar">`
 * element via the real Sidebar component.
 *
 * Concrete paths verified here mirror the Phase 8 R2#1 fix list:
 *   /dashboard           → new shell (sidebar visible)
 *   /sources             → new shell
 *   /keywords            → new shell
 *   /jobs                → new shell
 *   /digests             → new shell
 *   /settings            → new shell
 *   /followed-up/:uid    → new shell
 *   /hotspot/:id         → new shell
 *   /input               → old shell (legacy AppHeader visible)
 *   /tasks               → old shell (legacy AppHeader visible)
 *
 * DOM markers:
 *   Sidebar.vue renders <aside class="app-sidebar">
 *   AppHeader.vue renders <header class="app-header">
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import App from '../../src/App.vue'
import DashboardView from '../../src/views/DashboardView.vue'
import SourcesView from '../../src/views/SourcesView.vue'
import KeywordsView from '../../src/views/KeywordsView.vue'
import JobsView from '../../src/views/JobsView.vue'
import DigestsView from '../../src/views/DigestsView.vue'
import SettingsView from '../../src/views/SettingsView.vue'
import InputView from '../../src/views/InputView.vue'
import TasksView from '../../src/views/TasksView.vue'
import FollowDetailView from '../../src/views/FollowDetailView.vue'
import HotspotDetailView from '../../src/views/HotspotDetailView.vue'
import { ROUTES } from '../../src/router'

vi.mock('../../src/api/followedUp', () => ({
  listFollowed: vi.fn().mockResolvedValue([]),
  createFollowed: vi.fn(),
  deleteFollowed: vi.fn(),
  syncFollowed: vi.fn(),
}))
vi.mock('../../src/api/followDetail', () => ({
  fetchOverview: vi.fn().mockResolvedValue({
    display_name: 'mock',
    uid: 'mock',
    profile_url: '',
    platform: 'bilibili',
    health: { health: 'healthy', fetch_interval_minutes: 30, status: 'active', last_checked_at: null, last_error: null },
    recent_collections: [],
    recent_jobs: [],
    recent_events: [],
  }),
}))
vi.mock('../../src/api/settings', () => ({
  getSettings: vi.fn().mockResolvedValue({}),
  patchSettings: vi.fn().mockResolvedValue({}),
}))
vi.mock('../../src/api/sources', () => ({ listSources: vi.fn().mockResolvedValue([]) }))
vi.mock('../../src/api/keywords', () => ({ listKeywords: vi.fn().mockResolvedValue([]) }))
vi.mock('../../src/api/digests', () => ({ listDigests: vi.fn().mockResolvedValue([]) }))
vi.mock('../../src/api/jobs', () => ({ listJobs: vi.fn().mockResolvedValue([]) }))

async function renderAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ROUTES,
  })
  await router.push(path).catch(() => undefined)
  await router.isReady()

  return mount(App, {
    global: {
      plugins: [router],
      stubs: {
        DashboardView,
        SourcesView,
        KeywordsView,
        JobsView,
        DigestsView,
        SettingsView: { template: '<div data-testid="stub-settings" />' },
        FollowDetailView: { template: '<div data-testid="stub-follow" />' },
        HotspotDetailView: { template: '<div data-testid="stub-hotspot" />' },
        InputView: { template: '<div data-testid="stub-input" />' },
        TasksView: { template: '<div data-testid="stub-tasks" />' },
      },
    },
  })
}

describe('App.vue — usesNewShell routing (R2#1)', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it.each([
    '/dashboard',
    '/sources',
    '/keywords',
    '/jobs',
    '/digests',
    '/settings',
    '/followed-up/dfc-test-uid',
    '/hotspot/dfc-test-id',
    '/some-unknown-future-route',
  ])('renders Sidebar shell on %s', async (path) => {
    const wrapper = await renderAt(path)
    expect(wrapper.find('aside.app-sidebar').exists()).toBe(true)
    expect(wrapper.find('header.app-header').exists()).toBe(false)
    wrapper.unmount()
  })

  it.each(['/input', '/tasks'])(
    'renders legacy AppHeader on %s (Tauri-only windows keep old shell)',
    async (path) => {
      const wrapper = await renderAt(path)
      expect(wrapper.find('header.app-header').exists()).toBe(true)
      expect(wrapper.find('aside.app-sidebar').exists()).toBe(false)
      wrapper.unmount()
    },
  )
})
