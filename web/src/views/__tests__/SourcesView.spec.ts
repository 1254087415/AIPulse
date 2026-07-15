import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import SourcesView from '../SourcesView.vue'
import type { Source } from '../../types'

const { mockFetchSources, mockUpdateSource, mockSyncSource } = vi.hoisted(() => ({
  mockFetchSources: vi.fn().mockResolvedValue({ data: [] }),
  mockUpdateSource: vi.fn().mockResolvedValue({ data: {} }),
  mockSyncSource: vi.fn().mockResolvedValue({ data: { job_id: 'job-1', source_id: 'source-1' } }),
}))

vi.mock('../../composables/useSse', () => ({
  useSse: vi.fn(),
}))

vi.mock('../../api/sources', () => ({
  fetchSources: () => mockFetchSources(),
  updateSource: (sourceId: string, payload: Record<string, unknown>, _context?: unknown) =>
    mockUpdateSource(sourceId, payload),
  syncSource: (sourceId: string, _context?: unknown) => mockSyncSource(sourceId),
}))

const mockSource: Source = {
  id: 'source-1',
  name: 'Test Source',
  source_type: 'rss',
  collector_class: 'RssCollector',
  config: { feed_url: 'https://example.com/feed.xml' },
  default_weight: 1.0,
  fetch_interval_minutes: 60,
  is_active: true,
  last_fetched_at: '2026-07-14T10:00:00.000Z',
  last_error: null,
  failed_at: null,
  created_at: '2026-07-01T00:00:00.000Z',
  updated_at: '2026-07-14T10:00:00.000Z',
}

function mountSourcesView(queryClient: QueryClient) {
  return mount(SourcesView, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
    },
  })
}

describe('SourcesView', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
    mockFetchSources.mockResolvedValue({ data: [mockSource] })
    vi.clearAllMocks()
  })

  it('renders the source list', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    expect(wrapper.find('h1').text()).toBe('来源')
    expect(wrapper.text()).toContain('Test Source')
    expect(wrapper.text()).toContain('权重 1.0')
    expect(wrapper.text()).toContain('每 60 分钟')
  })

  it('shows the edit form when the edit button is clicked', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="source-weight"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="source-interval"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="source-config"]').exists()).toBe(true)
    expect((wrapper.find('[data-testid="source-weight"]').element as HTMLInputElement).value).toBe('1')
    expect((wrapper.find('[data-testid="source-interval"]').element as HTMLInputElement).value).toBe('60')
  })

  it('saves weight, interval, and config changes', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    const weightInput = wrapper.find('[data-testid="source-weight"]')
    const intervalInput = wrapper.find('[data-testid="source-interval"]')
    const configInput = wrapper.find('[data-testid="source-config"]')

    await weightInput.setValue('2.5')
    await intervalInput.setValue('30')
    await configInput.setValue('{"feed_url":"https://updated.example.com/feed.xml"}')

    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).toHaveBeenCalledWith(mockSource.id, {
      default_weight: 2.5,
      fetch_interval_minutes: 30,
      config: { feed_url: 'https://updated.example.com/feed.xml' },
    })
  })

  it('exits edit mode after a successful save', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-interval"]').setValue('30')
    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="source-weight"]').exists()).toBe(false)
  })

  it('stays in edit mode and shows the update error when saving fails', async () => {
    mockUpdateSource.mockRejectedValueOnce(new Error('保存失败'))
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-interval"]').setValue('30')
    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).toHaveBeenCalled()
    expect(wrapper.find('[data-testid="source-weight"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="update-error"]').text()).toContain('保存失败')
  })

  it('does not save when config JSON is invalid', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-config"]').setValue('{invalid json}')

    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="config-error"]').text()).toContain('JSON')
  })

  it('does not save when fetch interval is less than 5 minutes', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-interval"]').setValue('3')
    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="interval-validation-error"]').text()).toContain('5')
  })

  it('does not save when default weight is negative', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-weight"]').setValue('-1')
    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="weight-validation-error"]').text()).toContain('权重')
  })

  it('exits edit mode when cancel is clicked', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-weight"]').setValue('5')
    await wrapper.find('[data-testid="cancel-edit"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="source-weight"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('权重 1.0')
  })

  it('toggles source active state', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    const toggleButton = wrapper.find('[data-testid="toggle-source"]')
    expect(toggleButton.text()).toBe('停用')
    await toggleButton.trigger('click')
    await flushPromises()

    expect(mockUpdateSource).toHaveBeenCalledWith(mockSource.id, { is_active: false })
  })

  it('triggers immediate sync', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    const syncButton = wrapper.find('[data-testid="sync-source"]')
    expect(syncButton.text()).toBe('立即同步')
    await syncButton.trigger('click')
    await flushPromises()

    expect(mockSyncSource).toHaveBeenCalledWith(mockSource.id)
  })

  it('renders a sync error when immediate sync fails', async () => {
    mockSyncSource.mockRejectedValueOnce(new Error('同步失败'))
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="sync-source"]').trigger('click')
    await flushPromises()

    expect(mockSyncSource).toHaveBeenCalledWith(mockSource.id)
    expect(wrapper.find('[data-testid="sync-error"]').text()).toContain('同步失败')
  })

  it('formats an invalid last_fetched_at as never synced', async () => {
    mockFetchSources.mockResolvedValue({ data: [{ ...mockSource, last_fetched_at: 'invalid-date' }] })
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    expect(wrapper.text()).toContain('上次同步：从未同步')
  })

  it('rejects fetch interval of 4 minutes (one below minimum)', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-interval"]').setValue('4')
    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="interval-validation-error"]').text()).toContain('5')
  })

  it('accepts fetch interval of 5 minutes (at minimum)', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-interval"]').setValue('5')
    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).toHaveBeenCalledWith(mockSource.id, expect.objectContaining({ fetch_interval_minutes: 5 }))
  })

  it('rejects default weight of -0.1 (just below minimum)', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-weight"]').setValue('-0.1')
    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="weight-validation-error"]').text()).toContain('权重')
  })

  it('accepts default weight of 0 (at minimum)', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-weight"]').setValue('0')
    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).toHaveBeenCalledWith(mockSource.id, expect.objectContaining({ default_weight: 0 }))
  })

  it('accepts empty object config', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-config"]').setValue('{}')
    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).toHaveBeenCalledWith(mockSource.id, expect.objectContaining({ config: {} }))
  })

  it('rejects config that is a JSON array', async () => {
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    await wrapper.find('[data-testid="edit-source"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="source-config"]').setValue('[1, 2, 3]')
    await wrapper.find('[data-testid="save-source"]').trigger('click')
    await flushPromises()

    expect(mockUpdateSource).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="config-error"]').text()).toContain('配置必须是 JSON 对象')
  })

  it('shows empty state when no sources are configured', async () => {
    mockFetchSources.mockResolvedValue({ data: [] })
    const wrapper = mountSourcesView(queryClient)
    await flushPromises()

    expect(wrapper.find('.state-empty').exists()).toBe(true)
    expect(wrapper.find('.state-empty').text()).toContain('还没有配置来源')
  })
})
