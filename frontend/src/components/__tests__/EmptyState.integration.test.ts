import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EmptyState from '../ui/EmptyState.vue'
import DigestsView from '../../views/DigestsView.vue'
import JobsView from '../../views/JobsView.vue'
import KeywordsView from '../../views/KeywordsView.vue'
import SourcesView from '../../views/SourcesView.vue'
import DashboardHotspotPanel from '../../views/panels/DashboardHotspotPanel.vue'
import FollowUpcomingPanel from '../../views/panels/FollowUpcomingPanel.vue'

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  listPendingHotspots: vi.fn(),
}))

vi.mock('../../lib/apiFetch', () => ({ apiFetch: mocks.apiFetch }))
vi.mock('../../api/summaryJobs', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../api/summaryJobs')>()
  return { ...original, listPendingHotspots: mocks.listPendingHotspots }
})

function mountView(component: Parameters<typeof mount>[0]) {
  return mount(component, {
    global: {
      stubs: {
        PageHeader: true,
        SummarizeButton: true,
      },
    },
  })
}

async function mountEmptyApiView(component: Parameters<typeof mount>[0]) {
  mocks.apiFetch.mockResolvedValue({ success: true, data: [], meta: { total: 0, page: 1, limit: 20 } })
  const wrapper = mountView(component)
  await flushPromises()
  return wrapper
}

describe('EmptyState integrations', () => {
  beforeEach(() => {
    mocks.apiFetch.mockReset()
    mocks.listPendingHotspots.mockReset()
  })

  it('renders the shared empty state on keywords', async () => {
    const wrapper = await mountEmptyApiView(KeywordsView)
    const empty = wrapper.findComponent(EmptyState)

    expect(empty.props('title')).toBe('暂无关键词')
    expect(empty.props('description')).toContain('筛选内容')
  })

  it('renders the shared empty state on sources', async () => {
    const wrapper = await mountEmptyApiView(SourcesView)
    expect(wrapper.findComponent(EmptyState).props('title')).toBe('暂无来源')
  })

  it('renders the shared empty state on scheduled jobs', async () => {
    const wrapper = await mountEmptyApiView(JobsView)
    expect(wrapper.findComponent(EmptyState).props('title')).toBe('暂无定时任务')
  })

  it('renders the shared empty state when there are no digests', async () => {
    const wrapper = await mountEmptyApiView(DigestsView)
    expect(wrapper.findComponent(EmptyState).props('title')).toBe('暂无摘要')
  })

  it('uses a compact empty state when a digest has no summary body', async () => {
    mocks.apiFetch.mockResolvedValue({
      success: true,
      data: [{ id: 'digest-1', title: '日报', created_at: '2026-07-29', summary: null }],
    })
    const wrapper = mountView(DigestsView)
    await flushPromises()

    const empty = wrapper.findComponent(EmptyState)
    expect(empty.props('title')).toBe('暂无摘要内容')
    expect(empty.props('compact')).toBe(true)
    expect(wrapper.text()).not.toContain('—')
  })

  it('renders the shared empty state for upcoming learning', async () => {
    mocks.listPendingHotspots.mockResolvedValue([])
    const wrapper = mountView(FollowUpcomingPanel)
    await flushPromises()

    expect(wrapper.findComponent(EmptyState).props('title')).toBe('暂无待学习内容')
  })

  it('guides an empty hotspot list to keyword management', async () => {
    const wrapper = await mountEmptyApiView(DashboardHotspotPanel)
    const empty = wrapper.findComponent(EmptyState)

    expect(empty.props('actionLabel')).toBe('前往添加关注词')
    expect(empty.props('actionHref')).toBe('/keywords')
  })
})
