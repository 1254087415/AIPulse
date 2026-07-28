/**
 * FollowDetailView — UP 主详情页（spec §6.12 视觉骨架 + 后端 overview 真实数据）
 *
 * 数据来源：GET /api/followed-up/{id}/overview
 *   - 基础信息（id / platform / uid / display_name / profile_url）
 *   - health 子对象
 *   - recent_collections（合集 accordion 用）
 *   - recent_jobs（最近 10 条总结任务）
 *   - recent_learning_events（最近 10 条学习事件）
 *
 * 契约要点：
 *   - HTTP 调用走 src/api/followDetail.ts（typed wrapper）
 *   - 不做 mock 后端；测试只验证"请求被发出 + 真实字段被渲染"
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory, type RouteRecordRaw } from 'vue-router'

const { fetchOverviewMock } = vi.hoisted(() => ({
  fetchOverviewMock: vi.fn(),
}))

vi.mock('../../src/api/followDetail', () => ({
  fetchOverview: (...args: unknown[]) => fetchOverviewMock(...args),
}))

import FollowDetailView from '../../src/views/FollowDetailView.vue'

async function mountWithRoute(uid: string) {
  const routes: RouteRecordRaw[] = [
    { path: '/followed-up/:uid', name: 'follow-detail', component: FollowDetailView, props: true },
  ]
  const router = createRouter({ history: createMemoryHistory(), routes })
  router.push(`/followed-up/${uid}`)
  await router.isReady()
  const wrapper = mount(FollowDetailView, {
    global: { plugins: [router] },
    props: { uid },
  })
  await flushPromises()
  return wrapper
}

const OVERVIEW_FIXTURE = {
  id: 'fup_abc123',
  platform: 'bilibili',
  uid: '12345',
  display_name: 'Example UP',
  profile_url: 'https://space.bilibili.com/12345',
  health: {
    health: 'healthy',
    last_checked_at: '2026-07-26T01:00:00+00:00',
    last_error: null,
    failed_at: null,
    is_active: true,
    fetch_interval_minutes: 30,
    status: 'active',
  },
  config: {},
  recent_jobs: [
    {
      id: 'job_1',
      video_id: 'BV1abc',
      status: 'done',
      title: '示例视频 #1',
      created_at: '2026-07-25T22:00:00+00:00',
      completed_at: '2026-07-25T22:10:00+00:00',
      error: null,
      note_path: '/vault/Notes/example.md',
    },
  ],
  recent_learning_events: [],
  recent_collections: [
    {
      id: 'col_1',
      title: 'LLM 入门合集',
      platform_collection_id: 'col-bili-1',
      description: '从零开始的 LLM 学习路径',
      video_count: 12,
      created_at: '2026-07-01T00:00:00+00:00',
    },
    {
      id: 'col_2',
      title: 'Web Dev',
      platform_collection_id: 'col-bili-2',
      description: null,
      video_count: 5,
      created_at: '2026-06-20T00:00:00+00:00',
    },
  ],
}

async function mountView() {
  return mountWithRoute('fup_abc123')
}

describe('FollowDetailView', () => {
  beforeEach(() => {
    fetchOverviewMock.mockReset()
    fetchOverviewMock.mockResolvedValue(OVERVIEW_FIXTURE)
  })

  it('calls fetchOverview with the route uid', async () => {
    const wrapper = await mountView()
    expect(fetchOverviewMock).toHaveBeenCalledTimes(1)
    expect(fetchOverviewMock).toHaveBeenCalledWith('fup_abc123')
    wrapper.unmount()
  })

  it('renders the UP 主 header (avatar slot + display name + platform)', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('[data-testid="follow-detail-name"]').text()).toBe('Example UP')
    expect(wrapper.find('[data-testid="follow-detail-platform"]').text()).toBe('bilibili')
    wrapper.unmount()
  })

  it('renders the metadata dl with mid / profile_url / strategy / interval / last_checked_at', async () => {
    const wrapper = await mountView()
    const text = wrapper.text()
    expect(text).toContain('12345')
    expect(text).toContain('https://space.bilibili.com/12345')
    expect(text).toContain('30 分钟')
    wrapper.unmount()
  })

  it('renders collections as accordion rows with count and title', async () => {
    const wrapper = await mountView()
    const rows = wrapper.findAll('[data-testid="collection-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('LLM 入门合集')
    expect(rows[0].text()).toContain('12')
    wrapper.unmount()
  })

  it('renders recent jobs with their title and status', async () => {
    const wrapper = await mountView()
    const jobs = wrapper.findAll('[data-testid="recent-job"]')
    expect(jobs.length).toBeGreaterThan(0)
    expect(jobs[0].text()).toContain('示例视频 #1')
    expect(jobs[0].text()).toContain('done')
    wrapper.unmount()
  })

  it('surfaces an error state when the overview request fails', async () => {
    fetchOverviewMock.mockReset()
    fetchOverviewMock.mockRejectedValueOnce(new Error('boom'))
    const wrapper = await mountWithRoute('fup_abc123')
    expect(wrapper.find('[data-testid="follow-detail-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('加载失败')
    wrapper.unmount()
  })

  it('shows a loading state until the overview request resolves', async () => {
    // The component sets isLoading = true before fetchOverview resolves. We
    // resolve slowly and check the loading DOM node before flushing.
    fetchOverviewMock.mockReset()
    let resolveFn: ((v: typeof OVERVIEW_FIXTURE) => void) | null = null
    fetchOverviewMock.mockReturnValueOnce(new Promise((resolve) => {
      resolveFn = resolve
    }))
    const wrapper = await mountWithRoute('fup_abc123')
    expect(wrapper.find('[data-testid="follow-detail-loading"]').exists()).toBe(true)
    resolveFn?.(OVERVIEW_FIXTURE)
    await flushPromises()
    wrapper.unmount()
  })
})