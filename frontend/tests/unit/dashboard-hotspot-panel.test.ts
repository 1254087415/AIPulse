import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'

const { apiFetchMock } = vi.hoisted(() => ({ apiFetchMock: vi.fn() }))

vi.mock('../../src/lib/apiFetch', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

import DashboardHotspotPanel from '../../src/views/panels/DashboardHotspotPanel.vue'

const createTestRouter = () =>
  createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', redirect: '/dashboard' },
      { path: '/dashboard', component: { template: '<div>Dashboard</div>' } },
      { path: '/hotspot/:id', name: 'hotspot-detail', component: { template: '<div>Hotspot</div>' }, props: true },
    ],
  })

describe('DashboardHotspotPanel', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('loads and renders real hotspot data', async () => {
    apiFetchMock.mockResolvedValue({
      success: true,
      data: [
        {
          id: 'hotspot-1',
          title: 'Kimi 发布新模型',
          summary: '真实热点摘要',
          source_type: 'news',
          heat_score: 88.5,
          importance: 'high',
          category: 'ai-models',
          published_at: '2026-07-28T00:00:00Z',
        },
      ],
      meta: { total: 1, page: 1, limit: 20 },
    })

    const router = createTestRouter()
    const wrapper = mount(DashboardHotspotPanel, { global: { plugins: [router] } })
    await flushPromises()

    expect(apiFetchMock).toHaveBeenCalledWith('/api/hotspots', {
      query: { page: '1', limit: '20', sort: 'published_at', order: 'desc' },
    })
    expect(wrapper.find('[data-testid="hotspot-list"]').text()).toContain('Kimi 发布新模型')
    expect(wrapper.text()).toContain('真实热点摘要')
    wrapper.unmount()
  })

  it('wraps each hotspot card in a RouterLink that targets /hotspot/{id}', async () => {
    apiFetchMock.mockResolvedValue({
      success: true,
      data: [
        { id: 'hotspot-1', title: 'A', summary: null, source_type: 'news', heat_score: 0, importance: 'low', category: null, published_at: '2026-07-28T00:00:00Z' },
        { id: 'hotspot-2', title: 'B', summary: null, source_type: 'news', heat_score: 0, importance: 'low', category: null, published_at: '2026-07-28T00:00:00Z' },
      ],
      meta: { total: 2, page: 1, limit: 20 },
    })

    const router = createTestRouter()
    const wrapper = mount(DashboardHotspotPanel, { global: { plugins: [router] } })
    await flushPromises()

    const links = wrapper.findAll('[data-testid^="hotspot-card-"]')
    expect(links).toHaveLength(2)
    expect(links[0].element.tagName).toBe('A')
    expect(links[0].attributes('href')).toBe('/hotspot/hotspot-1')
    expect(links[1].attributes('href')).toBe('/hotspot/hotspot-2')

    wrapper.unmount()
  })

  it('navigates to the hotspot detail view when a card is clicked', async () => {
    apiFetchMock.mockResolvedValue({
      success: true,
      data: [
        { id: 'hotspot-42', title: 'Click me', summary: null, source_type: 'news', heat_score: 0, importance: 'low', category: null, published_at: '2026-07-28T00:00:00Z' },
      ],
      meta: { total: 1, page: 1, limit: 20 },
    })

    const router = createTestRouter()
    await router.push('/dashboard')
    const wrapper = mount(DashboardHotspotPanel, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.find('[data-testid="hotspot-card-hotspot-42"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/hotspot/hotspot-42')

    wrapper.unmount()
  })
})
