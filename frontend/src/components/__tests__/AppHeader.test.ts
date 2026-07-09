import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import AppHeader from '../AppHeader.vue'

const createTestRouter = () =>
  createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', redirect: '/input' },
      { path: '/input', component: { template: '<div>Input</div>' } },
      { path: '/tasks', component: { template: '<div>Tasks</div>' } },
      { path: '/settings', component: { template: '<div>Settings</div>' } },
    ],
  })

describe('AppHeader', () => {
  let router: ReturnType<typeof createTestRouter>

  beforeEach(() => {
    router = createTestRouter()
  })

  it('renders AIPulse brand and three tab labels', async () => {
    const wrapper = mount(AppHeader, {
      global: { plugins: [router] },
    })
    await router.isReady()
    await flushPromises()

    expect(wrapper.text()).toContain('AIPulse')
    expect(wrapper.text()).toContain('输入')
    expect(wrapper.text()).toContain('任务')
    expect(wrapper.text()).toContain('设置')

    wrapper.unmount()
  })

  it('marks the current route tab as active', async () => {
    const wrapper = mount(AppHeader, {
      global: { plugins: [router] },
    })
    await router.isReady()
    await router.push('/tasks')
    await flushPromises()

    const activeTab = wrapper.find('.tab.active')
    expect(activeTab.exists()).toBe(true)
    expect(activeTab.text()).toBe('任务')

    wrapper.unmount()
  })
})
