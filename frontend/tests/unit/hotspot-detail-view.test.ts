import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'

const { apiFetchMock } = vi.hoisted(() => ({ apiFetchMock: vi.fn() }))

vi.mock('../../src/lib/apiFetch', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

import HotspotDetailView from '../../src/views/HotspotDetailView.vue'

const createTestRouter = () =>
  createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', redirect: '/hotspot/hotspot-1' },
      { path: '/hotspot/:id', name: 'hotspot-detail', component: HotspotDetailView, props: true },
    ],
  })

describe('HotspotDetailView', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('loads and maps the real /api/hotspots/{id} response fields', async () => {
    apiFetchMock.mockResolvedValue({
      success: true,
      data: {
        id: 'hotspot-1',
        title: 'Kimi 发布新模型',
        url: 'https://example.com/kimi',
        summary: '真实热点摘要',
        status: 'archived',
        source_type: 'bilibili_up',
        heat_score: 88.5,
        importance: 'high',
        category: 'ai-models',
        published_at: '2026-07-28T00:00:00Z',
      },
    })

    const router = createTestRouter()
    await router.push('/hotspot/hotspot-1')
    await router.isReady()
    const wrapper = mount(HotspotDetailView, { global: { plugins: [router] } })
    await flushPromises()

    expect(apiFetchMock).toHaveBeenCalledWith('/api/hotspots/hotspot-1')
    expect(wrapper.find('.hotspot-card__title').text()).toBe('Kimi 发布新模型')
    expect(wrapper.find('[data-testid="hotspot-source"]').text()).toBe('B 站 UP 主')
    expect(wrapper.find('[data-testid="hotspot-status"]').text()).toBe('已归档')
    expect(wrapper.find('[data-testid="hotspot-importance"]').text()).toBe('高')
    expect(wrapper.find('[data-testid="hotspot-category"]').text()).toBe('ai-models')
    expect(wrapper.find('[data-testid="hotspot-score"]').text()).toBe('88.5')
    expect(wrapper.find('[data-testid="hotspot-published"]').text()).toBe('2026-07-28 08:00')
    expect(wrapper.text()).toContain('真实热点摘要')
    expect(wrapper.find('a').attributes('href')).toBe('https://example.com/kimi')
    wrapper.unmount()
  })
})
