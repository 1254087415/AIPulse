import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiFetchMock } = vi.hoisted(() => ({ apiFetchMock: vi.fn() }))

vi.mock('../../src/lib/apiFetch', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

import DashboardHotspotPanel from '../../src/views/panels/DashboardHotspotPanel.vue'

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

    const wrapper = mount(DashboardHotspotPanel)
    await flushPromises()

    expect(apiFetchMock).toHaveBeenCalledWith('/api/hotspots', {
      query: { page: '1', limit: '20', sort: 'published_at', order: 'desc' },
    })
    expect(wrapper.find('[data-testid="hotspot-list"]').text()).toContain('Kimi 发布新模型')
    expect(wrapper.text()).toContain('真实热点摘要')
    wrapper.unmount()
  })
})
