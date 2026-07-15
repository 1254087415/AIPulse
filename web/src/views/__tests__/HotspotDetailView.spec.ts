import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import HotspotDetailView from '../HotspotDetailView.vue'
import type { Hotspot } from '../../types'

const hotspotId = 'hotspot-1'

const mockHotspot: Hotspot = {
  id: hotspotId,
  title: 'Test Hotspot Title',
  url: 'https://example.com/article',
  summary: 'This is a test summary.',
  source_type: 'news',
  heat_score: 85.5,
  importance: 'high',
  category: 'ai-models',
  published_at: '2024-01-15T08:30:00.000Z',
}

const mockRelatedHotspots: Hotspot[] = [
  {
    id: 'hotspot-2',
    title: 'Related One',
    url: 'https://example.com/related-1',
    summary: 'Related summary one.',
    source_type: 'github',
    heat_score: 72.0,
    importance: 'medium',
    category: 'ai-products',
    published_at: '2024-01-14T10:00:00.000Z',
  },
]

const { mockFetchHotspot, mockFetchRelatedHotspots, mockArchiveHotspot, mockRoute } = vi.hoisted(() => ({
  mockFetchHotspot: vi.fn(async (_id: string): Promise<{ data: Hotspot }> => ({
    data: mockHotspot,
  })),
  mockFetchRelatedHotspots: vi.fn(async (_id: string): Promise<{ data: Hotspot[] }> => ({
    data: mockRelatedHotspots,
  })),
  mockArchiveHotspot: vi.fn(async (_id: string): Promise<{ data: { source_note_path: string; summary_note_path: string } }> => ({
    data: { source_note_path: 's', summary_note_path: 'm' },
  })),
  mockRoute: { params: { id: 'hotspot-1' } },
}))

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({ back: vi.fn() }),
}))

vi.mock('../../composables/useSse', () => ({
  useSse: vi.fn(),
}))

vi.mock('../../api/hotspots', () => ({
  fetchHotspot: (id: string) => mockFetchHotspot(id),
  fetchRelatedHotspots: (id: string) => mockFetchRelatedHotspots(id),
  archiveHotspot: (id: string) => mockArchiveHotspot(id),
}))

function mountDetailView(queryClient: QueryClient) {
  return mount(HotspotDetailView, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
      stubs: {
        HotspotList: {
          template: '<div data-testid="related-list-stub" />',
        },
      },
    },
  })
}

describe('HotspotDetailView', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
    mockFetchHotspot.mockClear()
    mockFetchRelatedHotspots.mockClear()
    mockArchiveHotspot.mockClear()
  })

  afterEach(() => {
    queryClient.clear()
  })

  it('renders hotspot title and summary', async () => {
    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    expect(wrapper.find('h1').text()).toBe(mockHotspot.title)
    expect(wrapper.find('.summary').text()).toBe(mockHotspot.summary)
    expect(wrapper.find('.external-link').attributes('href')).toBe(mockHotspot.url)
  })

  it('renders related hotspots list', async () => {
    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    expect(wrapper.find('[data-testid="related-list-stub"]').exists()).toBe(true)
  })

  it('calls archiveHotspot when archive button is clicked', async () => {
    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    await wrapper.find('.detail-actions button').trigger('click')
    await flushPromises()

    expect(mockArchiveHotspot).toHaveBeenCalledWith(hotspotId)
  })

  it('shows error state when archive fails', async () => {
    mockArchiveHotspot.mockRejectedValueOnce(new Error('archive failed'))

    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    await wrapper.find('.detail-actions button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.state-error').exists()).toBe(true)
    expect(wrapper.find('.state-error').text()).toContain('archive failed')
  })

  it('shows loading state while fetching hotspot', async () => {
    let resolveFetch: (value: { data: Hotspot }) => void = () => {}
    mockFetchHotspot.mockImplementationOnce(
      () =>
        new Promise<{ data: Hotspot }>((resolve) => {
          resolveFetch = resolve
        }),
    )

    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    expect(wrapper.find('.state-loading').exists()).toBe(true)
    expect(wrapper.find('.state-loading').text()).toContain('正在同步信号')

    resolveFetch({ data: mockHotspot })
    await flushPromises()

    expect(wrapper.find('.state-loading').exists()).toBe(false)
  })

  it('does not render external link for unsafe URLs', async () => {
    mockFetchHotspot.mockResolvedValueOnce({
      data: { ...mockHotspot, url: 'javascript:alert(1)' },
    })

    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    expect(wrapper.find('a.external-link').exists()).toBe(false)
    expect(wrapper.text()).toContain('链接不可用')
  })

  it('does not render external link for data scheme URLs', async () => {
    mockFetchHotspot.mockResolvedValueOnce({
      data: { ...mockHotspot, url: 'data:text/html,<script>alert(1)</script>' },
    })

    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    expect(wrapper.find('a.external-link').exists()).toBe(false)
    expect(wrapper.text()).toContain('链接不可用')
  })

  it('does not render external link for relative URLs', async () => {
    mockFetchHotspot.mockResolvedValueOnce({
      data: { ...mockHotspot, url: '/relative/path' },
    })

    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    expect(wrapper.find('a.external-link').exists()).toBe(false)
    expect(wrapper.text()).toContain('链接不可用')
  })

  it('shows archive success hint after successful archive', async () => {
    mockArchiveHotspot.mockResolvedValueOnce({ data: { source_note_path: 's', summary_note_path: 'm' } })

    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    await wrapper.find('.detail-actions button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.archive-hint').exists()).toBe(true)
    expect(wrapper.find('.archive-hint').text()).toContain('已归档')
  })

  it('does not render related section when related hotspots are empty', async () => {
    mockFetchRelatedHotspots.mockResolvedValueOnce({ data: [] })

    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    expect(wrapper.find('section.related').exists()).toBe(false)
    expect(wrapper.find('[data-testid="related-list-stub"]').exists()).toBe(false)
  })

  it('handles empty route id gracefully', async () => {
    mockRoute.params.id = ''
    mockFetchHotspot.mockClear()

    const wrapper = mountDetailView(queryClient)
    await flushPromises()

    expect(mockFetchHotspot).not.toHaveBeenCalled()
    expect(wrapper.find('.state-error').exists()).toBe(true)

    mockRoute.params.id = hotspotId
  })
})
