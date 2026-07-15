import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import DigestsView from '../DigestsView.vue'
import { generateDigest } from '../../api/digests'

vi.mock('../../api/digests', () => ({
  fetchDigests: vi.fn().mockResolvedValue({ data: [] }),
  fetchLatestDigest: vi.fn().mockResolvedValue({
    data: {
      id: 'digest-1',
      date: '2026-07-14',
      title: 'AI 日报',
      content: '第一段\n第二段<script>alert(1)</script>\n第三段',
      top_hotspot_ids: [],
      generated_at: '2026-07-14T10:00:00.000Z',
      pushed_at: null,
    },
  }),
  generateDigest: vi.fn().mockResolvedValue({ data: {} }),
}))

describe('DigestsView', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    })
    vi.clearAllMocks()
  })

  it('renders digest content as plain text without executing HTML', async () => {
    const wrapper = mount(DigestsView, {
      global: { plugins: [[VueQueryPlugin, { queryClient }]] },
    })
    await flushPromises()

    const markdown = wrapper.find('.markdown')
    expect(markdown.exists()).toBe(true)
    expect(markdown.find('script').exists()).toBe(false)
    expect(markdown.text()).toContain('<script>alert(1)</script>')
    expect(markdown.findAll('p').length).toBeGreaterThanOrEqual(3)
  })

  it('displays an error message when generate digest fails', async () => {
    vi.mocked(generateDigest).mockRejectedValueOnce(new Error('生成服务不可用'))

    const wrapper = mount(DigestsView, {
      global: { plugins: [[VueQueryPlugin, { queryClient }]] },
    })
    await flushPromises()

    const button = wrapper.find('button')
    expect(button.exists()).toBe(true)
    await button.trigger('click')
    await flushPromises()

    const error = wrapper.findAll('.state-error').find((el) => el.text().includes('生成摘要失败'))
    expect(error?.exists()).toBe(true)
    expect(error?.text()).toContain('生成服务不可用')
  })

  it('shows empty state when no digests exist', async () => {
    const { fetchLatestDigest } = await import('../../api/digests')
    vi.mocked(fetchLatestDigest).mockResolvedValueOnce({ data: null as unknown as import('../../types').DailyDigest })
    vi.mocked(generateDigest).mockResolvedValue({ data: { id: '', date: '', title: '', content: '', top_hotspot_ids: [], generated_at: '', pushed_at: null } })

    const wrapper = mount(DigestsView, {
      global: { plugins: [[VueQueryPlugin, { queryClient }]] },
    })
    await flushPromises()

    expect(wrapper.find('.state-empty').exists()).toBe(true)
    expect(wrapper.find('.state-empty').text()).toContain('还没有每日摘要')
  })

  it('renders invalid generated_at as empty time text', async () => {
    const { fetchLatestDigest } = await import('../../api/digests')
    vi.mocked(fetchLatestDigest).mockResolvedValueOnce({
      data: {
        id: 'digest-2',
        date: '2026-07-14',
        title: 'Invalid Date Digest',
        content: 'content',
        top_hotspot_ids: [],
        generated_at: 'not-a-date',
        pushed_at: null,
      },
    })

    const wrapper = mount(DigestsView, {
      global: { plugins: [[VueQueryPlugin, { queryClient }]] },
    })
    await flushPromises()

    expect(wrapper.find('h2').text()).toBe('Invalid Date Digest')
    expect(wrapper.find('.digest-time').text()).toBe('')
  })

  it('renders img onerror payload as plain text without executing HTML', async () => {
    const { fetchLatestDigest } = await import('../../api/digests')
    vi.mocked(fetchLatestDigest).mockResolvedValueOnce({
      data: {
        id: 'digest-3',
        date: '2026-07-14',
        title: 'XSS Test',
        content: '安全内容\n<img src="x" onerror="alert(1)">\n结尾',
        top_hotspot_ids: [],
        generated_at: '2026-07-14T10:00:00.000Z',
        pushed_at: null,
      },
    })

    const wrapper = mount(DigestsView, {
      global: { plugins: [[VueQueryPlugin, { queryClient }]] },
    })
    await flushPromises()

    const markdown = wrapper.find('.markdown')
    expect(markdown.find('img').exists()).toBe(false)
    expect(markdown.text()).toContain('<img src="x" onerror="alert(1)">')
  })
})
