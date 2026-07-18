import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import DashboardView from '../DashboardView.vue'
import type { HotspotListPayload } from '../../api/hotspots'
import { mockRouteQuery } from './mockRouteQuery'

const { mockFetchHotspots, HOTSPOT_PAGE_LIMIT, mockPush } = vi.hoisted(() => ({
  mockFetchHotspots: vi.fn(async (_params: Record<string, string> = {}): Promise<HotspotListPayload> => ({
    data: [],
    meta: { total: 0, page: 1, limit: 20 },
  })),
  HOTSPOT_PAGE_LIMIT: 20,
  mockPush: vi.fn(),
}))

vi.mock('../../composables/useSse', () => ({
  useSse: vi.fn(),
}))

vi.mock('../../api/hotspots', () => ({
  fetchHotspots: (params: Record<string, string> = {}) => mockFetchHotspots(params),
  HOTSPOT_PAGE_LIMIT,
}))

vi.mock('vue-router', async () => {
  const { mockRouteQuery } = await import('./mockRouteQuery')
  return {
    useRoute: () => mockRouteQuery,
    useRouter: () => ({ push: mockPush, replace: mockPush }),
  }
})

const mountedWrappers: ReturnType<typeof mount>[] = []

function mountDashboard(queryClient: QueryClient) {
  const wrapper = mount(DashboardView, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
      stubs: {
        HotspotList: {
          template: '<div data-testid="hotspot-list-stub" />',
        },
      },
    },
  })
  mountedWrappers.push(wrapper)
  return wrapper
}

async function updateFilter(wrapper: ReturnType<typeof mountDashboard>, selector: string, value: string) {
  const select = wrapper.find(selector)
  await select.setValue(value)
  await flushPromises()
}

describe('DashboardView', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    vi.useFakeTimers()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
    mockFetchHotspots.mockReset().mockResolvedValue({
      data: [],
      meta: { total: 0, page: 1, limit: HOTSPOT_PAGE_LIMIT },
    })
    mockPush.mockClear()
    mockRouteQuery.query = {}
  })

  afterEach(() => {
    mountedWrappers.forEach((wrapper) => wrapper.unmount())
    mountedWrappers.length = 0
    vi.useRealTimers()
  })

  it('renders page title and filter controls', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()

    expect(wrapper.find('h1').text()).toBe('AI 热点')
    expect(wrapper.find('input[type="search"]').exists()).toBe(true)
    expect(wrapper.find('select[data-testid="source-filter"]').exists()).toBe(true)
    expect(wrapper.find('select[data-testid="importance-filter"]').exists()).toBe(true)
    expect(wrapper.find('select[data-testid="category-filter"]').exists()).toBe(true)
    expect(wrapper.find('select[data-testid="sort-select"]').exists()).toBe(true)
    expect(wrapper.find('button[data-testid="sort-order"]').exists()).toBe(true)
  })

  it('calls fetchHotspots with default params on mount', async () => {
    mountDashboard(queryClient)
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ page: '1', limit: String(HOTSPOT_PAGE_LIMIT) }))
  })

  it('includes selected source when source filter changes', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()
    mockFetchHotspots.mockClear()

    await updateFilter(wrapper, 'select[data-testid="source-filter"]', 'news')

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ source: 'news', page: '1' }))
  })

  it('includes selected importance when importance filter changes', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()
    mockFetchHotspots.mockClear()

    await updateFilter(wrapper, 'select[data-testid="importance-filter"]', 'high')

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ importance: 'high', page: '1' }))
  })

  it('includes selected category when category filter changes', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()
    mockFetchHotspots.mockClear()

    await updateFilter(wrapper, 'select[data-testid="category-filter"]', 'ai-products')

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ category: 'ai-products', page: '1' }))
  })

  it('includes search query when user types in search box after debounce', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()
    mockFetchHotspots.mockClear()

    const input = wrapper.find('input[type="search"]')
    await input.setValue('LLM')
    await flushPromises()

    expect(mockFetchHotspots).not.toHaveBeenCalledWith(expect.objectContaining({ q: 'LLM' }))

    vi.advanceTimersByTime(300)
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ q: 'LLM', page: '1' }))
  })

  it('toggles sort order when direction button is clicked', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()
    mockFetchHotspots.mockClear()

    await wrapper.find('button[data-testid="sort-order"]').trigger('click')
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ order: 'asc', page: '1' }))
  })

  it('increases page when next page button is clicked', async () => {
    mockFetchHotspots.mockResolvedValueOnce({
      data: [{ id: '1', title: 't', url: 'u', summary: null, source_type: 'news', heat_score: 1, importance: 'low', category: null, published_at: null }],
      meta: { total: 25, page: 1, limit: HOTSPOT_PAGE_LIMIT },
    })

    const wrapper = mountDashboard(queryClient)
    await flushPromises()
    mockFetchHotspots.mockClear()

    await wrapper.find('button[data-testid="next-page"]').trigger('click')
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ page: '2' }))
  })

  it('resets page to 1 when filter changes after navigating pages', async () => {
    mockFetchHotspots.mockResolvedValueOnce({
      data: [{ id: '1', title: 't', url: 'u', summary: null, source_type: 'news', heat_score: 1, importance: 'low', category: null, published_at: null }],
      meta: { total: 25, page: 1, limit: HOTSPOT_PAGE_LIMIT },
    })

    const wrapper = mountDashboard(queryClient)
    await flushPromises()

    await wrapper.find('button[data-testid="next-page"]').trigger('click')
    await flushPromises()
    mockFetchHotspots.mockClear()

    await updateFilter(wrapper, 'select[data-testid="source-filter"]', 'github')

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ source: 'github', page: '1' }))
  })

  it('does not show pagination when only one page exists', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()

    expect(wrapper.find('nav[data-testid="pagination"]').exists()).toBe(false)
  })

  it('shows loading state while fetching hotspots', async () => {
    let resolveFetch: (value: HotspotListPayload) => void = () => {}
    mockFetchHotspots.mockImplementationOnce(
      () =>
        new Promise<HotspotListPayload>((resolve) => {
          resolveFetch = resolve
        }),
    )

    const wrapper = mountDashboard(queryClient)
    await flushPromises()

    expect(wrapper.find('.state-loading').exists()).toBe(true)
    expect(wrapper.find('.state-loading').text()).toContain('正在同步信号')

    resolveFetch({
      data: [],
      meta: { total: 0, page: 1, limit: HOTSPOT_PAGE_LIMIT },
    })
    await flushPromises()

    expect(wrapper.find('.state-loading').exists()).toBe(false)
  })

  it('shows error state when fetch fails', async () => {
    mockFetchHotspots.mockRejectedValueOnce(new Error('network error'))

    const wrapper = mountDashboard(queryClient)
    await flushPromises()

    expect(wrapper.find('.state-error').exists()).toBe(true)
    expect(wrapper.find('.state-error').text()).toContain('network error')
  })

  it('shows empty state when no hotspots returned', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()

    expect(wrapper.find('.state-empty').exists()).toBe(true)
    expect(wrapper.find('.state-empty').text()).toContain('还没有热点')
  })

  it('shows pagination when total pages is greater than 1', async () => {
    mockFetchHotspots.mockResolvedValueOnce({
      data: [{ id: '1', title: 't', url: 'u', summary: null, source_type: 'news', heat_score: 1, importance: 'low', category: null, published_at: null }],
      meta: { total: 25, page: 1, limit: HOTSPOT_PAGE_LIMIT },
    })

    const wrapper = mountDashboard(queryClient)
    await flushPromises()

    expect(wrapper.find('nav[data-testid="pagination"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="page-info"]').text()).toBe('第 1 / 2 页')
  })

  it('disables previous page on first page and next page on last page', async () => {
    mockFetchHotspots.mockResolvedValue({
      data: [{ id: '1', title: 't', url: 'u', summary: null, source_type: 'news', heat_score: 1, importance: 'low', category: null, published_at: null }],
      meta: { total: 40, page: 1, limit: HOTSPOT_PAGE_LIMIT },
    })

    const wrapper = mountDashboard(queryClient)
    await flushPromises()

    await vi.waitFor(() => expect(wrapper.find('[data-testid="page-info"]').text()).toBe('第 1 / 2 页'))

    const prevButton = () => wrapper.find('button[aria-label="上一页"]').element as HTMLButtonElement
    const nextButton = () => wrapper.find('button[data-testid="next-page"]').element as HTMLButtonElement

    expect(prevButton().disabled).toBe(true)
    expect(nextButton().disabled).toBe(false)

    await wrapper.find('button[data-testid="next-page"]').trigger('click')
    await flushPromises()

    await vi.waitFor(() => expect(wrapper.find('[data-testid="page-info"]').text()).toBe('第 2 / 2 页'))

    expect(prevButton().disabled).toBe(false)
    expect(nextButton().disabled).toBe(true)
  })

  it('removes search query param when search input is cleared', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()

    const input = wrapper.find('input[type="search"]')
    await input.setValue('LLM')
    await flushPromises()
    vi.advanceTimersByTime(300)
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ q: 'LLM' }))

    mockFetchHotspots.mockClear()
    await input.setValue('')
    await flushPromises()
    vi.advanceTimersByTime(300)
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.not.objectContaining({ q: '' }))
    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ page: '1' }))
  })

  it('initializes filters from URL query and calls fetchHotspots', async () => {
    mockRouteQuery.query = { q: 'AI', source: 'github', page: '2' }

    mountDashboard(queryClient)
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(
      expect.objectContaining({ q: 'AI', source: 'github', page: '2' }),
    )
  })

  it('falls back to page 1 when URL page is invalid or non-positive', async () => {
    mockRouteQuery.query = { page: 'abc' }

    mountDashboard(queryClient)
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ page: '1' }))
  })

  it('uses default sort and order when URL omits them', async () => {
    mountDashboard(queryClient)
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'heat_score', order: 'desc', page: '1' }),
    )
  })

  it('combines multiple filters in a single fetchHotspots call', async () => {
    mockRouteQuery.query = { q: 'LLM', source: 'news', importance: 'high', category: 'ai-models' }

    mountDashboard(queryClient)
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(
      expect.objectContaining({
        q: 'LLM',
        source: 'news',
        importance: 'high',
        category: 'ai-models',
        page: '1',
      }),
    )
  })

  it('handles array query values by using the first element', async () => {
    mockRouteQuery.query = { source: ['github', 'news'] }

    mountDashboard(queryClient)
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ source: 'github' }))
  })

  it('writes URL query when filter changes', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()
    mockPush.mockClear()

    await updateFilter(wrapper, 'select[data-testid="source-filter"]', 'news')

    expect(mockPush).toHaveBeenCalledWith(expect.objectContaining({ query: { source: 'news' } }))
  })

  it('updates URL page when paginating', async () => {
    mockFetchHotspots.mockResolvedValueOnce({
      data: [{ id: '1', title: 't', url: 'u', summary: null, source_type: 'news', heat_score: 1, importance: 'low', category: null, published_at: null }],
      meta: { total: 25, page: 1, limit: HOTSPOT_PAGE_LIMIT },
    })

    const wrapper = mountDashboard(queryClient)
    await flushPromises()
    mockPush.mockClear()

    await wrapper.find('button[data-testid="next-page"]').trigger('click')
    await flushPromises()

    expect(mockPush).toHaveBeenCalledWith(expect.objectContaining({ query: { page: '2' } }))
  })

  it('resets page to 1 in URL when filter changes after navigating pages', async () => {
    mockFetchHotspots.mockResolvedValueOnce({
      data: [{ id: '1', title: 't', url: 'u', summary: null, source_type: 'news', heat_score: 1, importance: 'low', category: null, published_at: null }],
      meta: { total: 25, page: 1, limit: HOTSPOT_PAGE_LIMIT },
    })

    mockRouteQuery.query = { page: '2' }
    const wrapper = mountDashboard(queryClient)
    await flushPromises()
    mockPush.mockClear()

    await updateFilter(wrapper, 'select[data-testid="source-filter"]', 'github')

    expect(mockPush).toHaveBeenCalledWith(expect.objectContaining({ query: { source: 'github' } }))
  })

  it('updates filters and refetches when URL query changes', async () => {
    const wrapper = mountDashboard(queryClient)
    await flushPromises()
    mockFetchHotspots.mockClear()

    mockFetchHotspots.mockResolvedValueOnce({
      data: [{ id: '2', title: 'github item', url: 'u2', summary: null, source_type: 'github', heat_score: 2, importance: 'medium', category: 'ai-products', published_at: null }],
      meta: { total: 1, page: 1, limit: HOTSPOT_PAGE_LIMIT },
    })

    mockRouteQuery.query = { source: 'github' }
    await flushPromises()

    expect(mockFetchHotspots).toHaveBeenCalledWith(expect.objectContaining({ source: 'github' }))
    expect((wrapper.find('select[data-testid="source-filter"]').element as HTMLSelectElement).value).toBe('github')
    await vi.waitFor(() => expect(wrapper.find('.readout-value').text()).toBe('1'))
  })
})
