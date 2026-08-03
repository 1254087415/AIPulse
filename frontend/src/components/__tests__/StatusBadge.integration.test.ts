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
  listHotspots: vi.fn(),
}))

vi.mock('../../lib/apiFetch', () => ({ apiFetch: mocks.apiFetch }))
vi.mock('../../api/hotspots', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../api/hotspots')>()
  return { ...original, listHotspots: mocks.listHotspots }
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
    mocks.listHotspots.mockReset()
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

  it('uses warning and danger badges for pending and failed records', async () => {
    mocks.listHotspots.mockResolvedValue([
      {
        id: 'hotspot-1',
        title: '待处理热点',
        url: 'https://www.bilibili.com/video/BV1aaa',
        content_id: 'BV1aaa',
        up_name: 'UP',
        summary: null,
        source_type: 'bilibili_up',
        heat_score: 12,
        importance: 'medium',
        category: '模型',
        status: 'new',
        decision_status: 'pending',
        notified: false,
        obsidian_source_path: null,
        obsidian_summary_path: null,
        learning_event_id: null,
        created_at: '2026-07-24T11:05:00',
        published_at: '2026-07-24T10:05:00',
      },
      {
        id: 'hotspot-2',
        title: '失败热点',
        url: 'https://www.bilibili.com/video/BV1bbb',
        content_id: 'BV1bbb',
        up_name: 'UP',
        summary: null,
        source_type: 'bilibili_up',
        heat_score: 8,
        importance: 'low',
        category: '模型',
        status: 'new',
        decision_status: 'failed',
        notified: false,
        obsidian_source_path: null,
        obsidian_summary_path: null,
        learning_event_id: null,
        created_at: '2026-07-24T11:10:00',
        published_at: '2026-07-24T10:10:00',
      },
    ])
    const wrapper = mountView(FollowRecordsPanel)
    await flushPromises()

    const badges = wrapper.findAllComponents(StatusBadge)
    expect(badges.map((badge) => badge.props('tone'))).toEqual(['warning', 'danger'])
    expect(badges.map((badge) => badge.text())).toEqual(['等待处理', '失败'])
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
