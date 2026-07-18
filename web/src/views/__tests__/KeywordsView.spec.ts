import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import KeywordsView from '../../views/KeywordsView.vue'
import type { Keyword } from '../../types'

const { mockFetchKeywords, mockCreateKeyword, mockUpdateKeyword, mockDeleteKeyword } = vi.hoisted(() => ({
  mockFetchKeywords: vi.fn().mockResolvedValue({ data: [] }),
  mockCreateKeyword: vi.fn().mockResolvedValue({ data: {} }),
  mockUpdateKeyword: vi.fn().mockResolvedValue({ data: {} }),
  mockDeleteKeyword: vi.fn().mockResolvedValue({ data: { id: '' } }),
}))

vi.mock('../../api/keywords', () => ({
  fetchKeywords: () => mockFetchKeywords(),
  createKeyword: (value: string) => mockCreateKeyword(value),
  updateKeyword: (id: string, payload: Record<string, unknown>) => mockUpdateKeyword(id, payload),
  deleteKeyword: (id: string) => mockDeleteKeyword(id),
}))

vi.mock('../../composables/useSse', () => ({
  useSse: vi.fn(),
}))

function createKeyword(overrides: Partial<Keyword> = {}): Keyword {
  return {
    id: 'keyword-1',
    value: 'Kimi',
    is_active: true,
    notify_on_match: true,
    ...overrides,
  }
}

function mountKeywordsView(queryClient: QueryClient) {
  return mount(KeywordsView, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
    },
  })
}

describe('KeywordsView', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
    mockFetchKeywords.mockResolvedValue({ data: [] })
    vi.clearAllMocks()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders title and subtitle', async () => {
    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    expect(wrapper.find('h1').text()).toBe('关键词')
    expect(wrapper.text()).toContain('关注词与通知开关')
  })

  it('shows loading state while fetching keywords', async () => {
    let resolveFetch: (value: { data: Keyword[] }) => void = () => {}
    mockFetchKeywords.mockImplementationOnce(
      () => new Promise<{ data: Keyword[] }>((resolve) => {
        resolveFetch = resolve
      }),
    )

    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    expect(wrapper.find('.state-loading').exists()).toBe(true)

    resolveFetch({ data: [] })
    await flushPromises()

    expect(wrapper.find('.state-loading').exists()).toBe(false)
  })

  it('shows error state when fetching fails', async () => {
    mockFetchKeywords.mockRejectedValueOnce(new Error('backend down'))

    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    expect(wrapper.find('.state-error').exists()).toBe(true)
    expect(wrapper.find('.state-error').text()).toContain('backend down')
  })

  it('shows empty state when no keywords exist', async () => {
    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    expect(wrapper.find('.state-empty').exists()).toBe(true)
    expect(wrapper.find('.state-empty').text()).toContain('还没有关键词')
  })

  it('renders keyword count readout', async () => {
    mockFetchKeywords.mockResolvedValue({ data: [createKeyword(), createKeyword({ id: 'keyword-2' })] })

    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    expect(wrapper.find('[aria-label="已有关键词"]').text()).toContain('2')
  })

  it('creates a keyword when form is submitted', async () => {
    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('LLM')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mockCreateKeyword).toHaveBeenCalledWith('LLM')
  })

  it('does not submit when input is empty or whitespace', async () => {
    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('   ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(mockCreateKeyword).not.toHaveBeenCalled()
  })

  it('clears input after successful creation', async () => {
    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('Agent')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect((input.element as HTMLInputElement).value).toBe('')
  })

  it('disables input and button while creating', async () => {
    let resolveCreate: (value: { data: Keyword }) => void = () => {}
    mockCreateKeyword.mockImplementationOnce(
      () => new Promise<{ data: Keyword }>((resolve) => {
        resolveCreate = resolve
      }),
    )

    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('LLM')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect((input.element as HTMLInputElement).disabled).toBe(true)
    expect((wrapper.find('button').element as HTMLButtonElement).disabled).toBe(true)

    resolveCreate({ data: createKeyword() })
    await flushPromises()

    expect((input.element as HTMLInputElement).disabled).toBe(false)
  })

  it('shows creation error when createKeyword fails', async () => {
    mockCreateKeyword.mockRejectedValueOnce(new Error('duplicate'))

    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    await wrapper.find('input').setValue('LLM')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.state-error').text()).toContain('duplicate')
  })

  it('shows delete error when deleteKeyword fails', async () => {
    mockDeleteKeyword.mockRejectedValueOnce(new Error('delete failed'))
    const keyword = createKeyword()
    mockFetchKeywords.mockResolvedValue({ data: [keyword] })

    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    await wrapper.find('button.action-danger').trigger('click')
    await flushPromises()

    expect(mockDeleteKeyword).toHaveBeenCalledWith(keyword.id)
    expect(wrapper.find('#delete-error').exists()).toBe(true)
    expect(wrapper.find('#delete-error').text()).toContain('delete failed')
  })

  it('toggles notify_on_match when KeywordList emits toggleNotify', async () => {
    const keyword = createKeyword({ notify_on_match: true })
    mockFetchKeywords.mockResolvedValue({ data: [keyword] })

    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    await wrapper.find('.keyword-list button:first-of-type').trigger('click')
    await flushPromises()

    expect(mockUpdateKeyword).toHaveBeenCalledWith(keyword.id, { notify_on_match: false })
  })

  it('toggles is_active when KeywordList emits toggleActive', async () => {
    const keyword = createKeyword({ is_active: true })
    mockFetchKeywords.mockResolvedValue({ data: [keyword] })

    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    const buttons = wrapper.find('.keyword-list').findAll('button')
    await buttons[1].trigger('click')
    await flushPromises()

    expect(mockUpdateKeyword).toHaveBeenCalledWith(keyword.id, { is_active: false })
  })

  it('deletes keyword when KeywordList emits delete', async () => {
    const keyword = createKeyword()
    mockFetchKeywords.mockResolvedValue({ data: [keyword] })

    const wrapper = mountKeywordsView(queryClient)
    await flushPromises()

    await wrapper.find('button.action-danger').trigger('click')
    await flushPromises()

    expect(mockDeleteKeyword).toHaveBeenCalledWith(keyword.id)
  })
})
