import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FollowedUp } from '../../api/followedUp'
import FollowCard from '../follow-list-panel/FollowCard.vue'
import StatusBadge from '../ui/StatusBadge.vue'
import SourcesView from '../../views/SourcesView.vue'
import JobsView from '../../views/JobsView.vue'
import DashboardHotspotPanel from '../../views/panels/DashboardHotspotPanel.vue'
import FollowRecordsPanel from '../../views/panels/FollowRecordsPanel.vue'

const mocks = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  listSummaryJobs: vi.fn(),
}))

vi.mock('../../lib/apiFetch', () => ({ apiFetch: mocks.apiFetch }))
vi.mock('../../api/summaryJobs', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../api/summaryJobs')>()
  return { ...original, listSummaryJobs: mocks.listSummaryJobs }
})
vi.mock('../../lib/sse-client', () => ({ subscribeSse: () => () => undefined }))

const followed: FollowedUp = {
  id: 'follow-1',
  platform: 'bilibili',
  uid: '517327498',
  display_name: '测试 UP 主',
  profile_url: '',
  collector_strategy: 'uapi',
  last_cursor_id: null,
  fetch_interval_minutes: 30,
  is_active: true,
  status: 'active',
  health: 'healthy',
  last_checked_at: '2026-07-24T11:05:00',
  last_error: null,
  failed_at: null,
  created_at: '2026-07-24T03:00:00Z',
  updated_at: '2026-07-24T03:00:00Z',
  deleted_at: null,
}

function mountView(component: Parameters<typeof mount>[0]) {
  return mount(component, {
    global: {
      stubs: {
        AppButton: true,
        PageHeader: true,
        SummarizeButton: true,
      },
    },
  })
}

describe('StatusBadge integrations', () => {
  beforeEach(() => {
    mocks.apiFetch.mockReset()
    mocks.listSummaryJobs.mockReset()
  })

  it('uses badges for platform, enabled state, and health on followed cards', () => {
    const wrapper = mount(FollowCard, { props: { followed } })
    const badges = wrapper.findAllComponents(StatusBadge)

    expect(badges.map((badge) => badge.text())).toEqual(['B 站', '启用', '健康'])
    expect(badges.map((badge) => badge.props('tone'))).toEqual(['warning', 'success', 'success'])
    expect(wrapper.text()).toContain('2026-07-24 11:05')
    expect(wrapper.text()).toContain('30 分钟')
    expect(wrapper.text()).not.toContain('分钟 / 次')
    expect(wrapper.text()).not.toContain('uid:')
  })

  it('uses a success badge for enabled sources', async () => {
    mocks.apiFetch.mockResolvedValue({
      success: true,
      data: [{
        id: 'source-1', name: 'B 站', source_type: 'bilibili_up', collector_class: 'Collector',
        default_weight: 1, fetch_interval_minutes: 30, is_active: true,
        last_fetched_at: '2026-07-24T11:05:00', last_error: null,
      }],
    })
    const wrapper = mountView(SourcesView)
    await flushPromises()

    const badge = wrapper.findComponent(StatusBadge)
    expect(badge.text()).toBe('启用')
    expect(badge.props('tone')).toBe('success')
    expect(wrapper.text()).toContain('2026-07-24 11:05')
    expect(wrapper.text()).toContain('30 分钟')
  })

  it('uses warning and danger badges for partial and failed records', async () => {
    mocks.listSummaryJobs.mockResolvedValue([
      { id: 'job-1', video_id: 'BV1', title: '部分任务', up_name: 'UP', status: 'partial', error: null, note_path: null, created_at: '2026-07-24T11:05:00' },
      { id: 'job-2', video_id: 'BV2', title: '失败任务', up_name: 'UP', status: 'failed', error: 'error', note_path: null, created_at: null },
    ])
    const wrapper = mountView(FollowRecordsPanel)
    await flushPromises()

    const badges = wrapper.findAllComponents(StatusBadge)
    expect(badges.map((badge) => badge.props('tone'))).toEqual(['warning', 'danger'])
    expect(badges.map((badge) => badge.text())).toEqual(['部分完成', '失败'])
    expect(wrapper.text()).toContain('2026-07-24 11:05')
  })

  it('uses a warning badge for medium importance', async () => {
    mocks.apiFetch.mockResolvedValue({
      success: true,
      data: [{ id: 'hotspot-1', title: '热点', summary: null, source_type: 'bilibili_up', heat_score: 0, importance: 'medium', category: '模型发布', published_at: '2026-07-24T11:05:00' }],
      meta: { total: 1, page: 1, limit: 20 },
    })
    const wrapper = mountView(DashboardHotspotPanel)
    await flushPromises()

    const badge = wrapper.findComponent(StatusBadge)
    expect(badge.props('tone')).toBe('warning')
    expect(badge.text()).toBe('中')
    expect(wrapper.find('[data-testid="hotspot-source"]').text()).toBe('B 站 UP 主')
    expect(wrapper.find('[data-testid="hotspot-category"]').text()).toBe('模型发布')
    const published = wrapper.find('[data-testid="hotspot-published"]')
    expect(published.text()).toBe('2026-07-24 11:05')
    expect(published.attributes('datetime')).toBe('2026-07-24T11:05:00')
    expect(wrapper.find('[data-testid="hotspot-score"]').exists()).toBe(false)
    expect(wrapper.findAll('.hotspot-card__tag')).toHaveLength(3)
  })

  it('uses a neutral badge for scheduled job triggers', async () => {
    mocks.apiFetch.mockResolvedValue({
      success: true,
      data: [{ id: 'scan', name: 'sync_all_sources', func: 'aipulse.scheduler.jobs.hotspot_sync:sync_all_sources', trigger: 'interval[0:30:00]', next_run_time: '2026-07-24T11:05:00' }],
    })
    const wrapper = mountView(JobsView)
    await flushPromises()

    const badge = wrapper.findComponent(StatusBadge)
    expect(badge.text()).toBe('每 30 分钟')
    expect(badge.props('tone')).toBe('neutral')
    expect(wrapper.text()).toContain('同步全部来源')
    expect(wrapper.text()).not.toContain('sync_all_sources')
    expect(wrapper.get('.job-row__name').attributes('title')).toBe('aipulse.scheduler.jobs.hotspot_sync:sync_all_sources')
    expect(wrapper.text()).toContain('2026-07-24 11:05')
  })
})
