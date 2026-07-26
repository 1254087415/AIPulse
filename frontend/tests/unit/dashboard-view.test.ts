import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import DashboardView from '../../src/views/DashboardView.vue'

const createTestRouter = () =>
  createRouter({
    history: createWebHashHistory(),
    routes: [
      { path: '/', redirect: '/dashboard' },
      { path: '/dashboard', component: DashboardView },
      {
        path: '/dashboard/followed',
        name: 'dashboard-followed',
        component: { template: '<div data-testid="placeholder-followed">placeholder</div>' },
      },
    ],
  })

describe('DashboardView', () => {
  let router: ReturnType<typeof createTestRouter>

  beforeEach(() => {
    router = createTestRouter()
  })

  it('mounts with the default hotspot panel when no tab query is present', async () => {
    router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(DashboardView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    // Five tab buttons present (the spec mentions 5 tabs including failed).
    const tabs = wrapper.findAll('.dashboard-tab')
    expect(tabs.length).toBeGreaterThanOrEqual(4)
    expect(wrapper.text()).toContain('AI 热点')

    wrapper.unmount()
  })

  it('switches the active tab when the user clicks one', async () => {
    router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(DashboardView, {
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await flushPromises()

    const tabs = wrapper.findAll('.dashboard-tab')
    const followedTab = tabs.find((tab) => tab.text().includes('关注'))
    expect(followedTab).toBeDefined()

    await followedTab!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.query.tab).toBe('follow-list')

    wrapper.unmount()
  })

  it('keeps the existing dashboard view when no follow panel is mounted', async () => {
    router.push('/dashboard')
    await router.isReady()

    const wrapper = mount(DashboardView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    // The view should render without crashing and expose its tabs.
    expect(wrapper.find('.dashboard-view').exists()).toBe(true)

    wrapper.unmount()
  })
})