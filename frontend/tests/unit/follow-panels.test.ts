import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { apiFetchMock } = vi.hoisted(() => ({ apiFetchMock: vi.fn() }))

vi.mock('../../src/lib/apiFetch', () => ({ apiFetch: apiFetchMock }))

import { listSummaryJobs } from '../../src/api/summaryJobs'
import { listHotspots } from '../../src/api/hotspots'
import FollowRecordsPanel from '../../src/views/panels/FollowRecordsPanel.vue'
import FollowUpcomingPanel from '../../src/views/panels/FollowUpcomingPanel.vue'
import FollowFailedPanel from '../../src/views/panels/FollowFailedPanel.vue'

const job = (overrides = {}) => ({
  id: 'job-1',
  video_id: 'BV1abc',
  title: 'AI 入门',
  up_name: '李沐',
  status: 'completed',
  error: null,
  note_path: 'AI/入门.md',
  created_at: '2026-07-26T08:00:00Z',
  ...overrides,
})

const hotspot = {
  id: 'hotspot-1',
  title: '待学习视频',
  url: 'https://www.bilibili.com/video/BV1hot',
  content_id: 'BV1hot',
  up_name: 'UP 主',
  source_type: 'bilibili_up',
  summary: 'summary',
  heat_score: 1.2,
  importance: 'medium',
  category: 'ai',
  status: 'new',
  decision_status: 'pending',
  notified: false,
  obsidian_source_path: null,
  obsidian_summary_path: null,
  learning_event_id: null,
  created_at: '2026-07-26T08:00:00Z',
  published_at: '2026-07-26T08:00:00Z',
}

describe('summary jobs API', () => {
  beforeEach(() => apiFetchMock.mockReset())

  it('lists jobs with the requested limit and optional status', async () => {
    apiFetchMock.mockResolvedValue({ success: true, data: [job()] })

    await listSummaryJobs({ limit: 20, status: 'failed' })

    expect(apiFetchMock).toHaveBeenCalledWith('/api/summary/jobs', {
      method: 'GET',
      query: { limit: '20', status: 'failed' },
    })
  })
})

describe('hotspots API', () => {
  beforeEach(() => apiFetchMock.mockReset())

  it('lists hotspot records with the requested filter and sort', async () => {
    apiFetchMock.mockResolvedValue({ success: true, data: [hotspot], meta: {} })

    await listHotspots({
      decisionStatus: 'pending,failed',
      limit: 50,
      page: 1,
      sort: 'created_at',
      order: 'desc',
    })

    expect(apiFetchMock).toHaveBeenCalledWith('/api/hotspots', {
      method: 'GET',
      query: {
        decision_status: 'pending,failed',
        limit: '50',
        page: '1',
        sort: 'created_at',
        order: 'desc',
      },
    })
  })
})

describe('follow panels', () => {
  beforeEach(() => apiFetchMock.mockReset())

  it('renders hotspot records and the status-driven action matrix', async () => {
    apiFetchMock.mockResolvedValue({
      success: true,
      data: [
        hotspot,
        {
          ...hotspot,
          id: 'hotspot-2',
          content_id: 'BV1learn',
          title: '值得学习',
          decision_status: 'worth_learning',
          created_at: '2026-07-26T09:00:00Z',
        },
        {
          ...hotspot,
          id: 'hotspot-3',
          content_id: 'BV1skip',
          title: '已跳过',
          decision_status: 'skipped',
          created_at: '2026-07-26T10:00:00Z',
        },
        {
          ...hotspot,
          id: 'hotspot-4',
          content_id: 'BV1fail',
          title: '失败项',
          decision_status: 'failed',
          created_at: '2026-07-26T11:00:00Z',
        },
        {
          ...hotspot,
          id: 'hotspot-5',
          content_id: 'BV1done',
          title: '已归档',
          decision_status: 'archived',
          obsidian_summary_path: '/vault/AIPulse/BV1done.md',
          created_at: '2026-07-26T12:00:00Z',
        },
      ],
      meta: {},
    })
    const wrapper = mount(FollowRecordsPanel)
    await flushPromises()

    expect(apiFetchMock).toHaveBeenCalledWith('/api/hotspots', {
      method: 'GET',
      query: {
        decision_status: 'pending,worth_learning,skipped,failed,archived,worth_notified',
        limit: '50',
        page: '1',
        sort: 'created_at',
        order: 'desc',
      },
    })
    expect(wrapper.text()).toContain('待学习视频')
    expect(wrapper.text()).toContain('值得学习')
    expect(wrapper.text()).toContain('已归档')
    expect(wrapper.find('[data-testid="process-hotspot-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="skip-hotspot-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="archive-hotspot-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="notify-hotspot-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="force-archive-hotspot-3"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="retry-hotspot-4"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="view-note-hotspot-5"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('renders pending hotspots in the upcoming panel', async () => {
    apiFetchMock.mockResolvedValue({ success: true, data: [hotspot], meta: {} })
    const wrapper = mount(FollowUpcomingPanel)
    await flushPromises()

    expect(apiFetchMock).toHaveBeenCalledWith('/api/hotspots', {
      method: 'GET',
      query: { decision_status: 'pending', page: '1', limit: '20' },
    })
    expect(wrapper.text()).toContain('待学习视频')
    expect(wrapper.findComponent({ name: 'SummarizeButton' }).exists()).toBe(true)
    wrapper.unmount()
  })

  it('skips a hotspot through the real PATCH endpoint', async () => {
    apiFetchMock
      .mockResolvedValueOnce({ success: true, data: [hotspot], meta: {} })
      .mockResolvedValueOnce({
        success: true,
        data: { ...hotspot, decision_status: 'skipped' },
      })
      .mockResolvedValueOnce({
        success: true,
        data: [{ ...hotspot, decision_status: 'skipped' }],
        meta: {},
      })
    const wrapper = mount(FollowRecordsPanel)
    await flushPromises()

    await wrapper.find('[data-testid="skip-hotspot-1"]').trigger('click')
    await flushPromises()

    expect(apiFetchMock).toHaveBeenNthCalledWith(2, '/api/hotspots/hotspot-1', {
      method: 'PATCH',
      body: '{"decision_status":"skipped"}',
    })
    wrapper.unmount()
  })

  it('renders failed jobs with the error and retry button', async () => {
    apiFetchMock.mockResolvedValue({ success: true, data: [
      job({ status: 'failed', error: '字幕获取失败' }),
      job({ id: 'job-2', video_id: 'BV1partial', status: 'partial', error: '部分步骤失败' }),
      job({ id: 'job-3', video_id: 'BV1timeout', status: 'timeout', error: '处理超时' }),
      job({ id: 'job-4', video_id: 'BV1done', status: 'completed', error: null }),
    ] })
    const wrapper = mount(FollowFailedPanel)
    await flushPromises()

    expect(apiFetchMock).toHaveBeenCalledWith('/api/summary/jobs', {
      method: 'GET',
      query: { limit: '20' },
    })
    expect(wrapper.text()).toContain('字幕获取失败')
    expect(wrapper.text()).toContain('部分步骤失败')
    expect(wrapper.text()).toContain('处理超时')
    expect(wrapper.text()).not.toContain('BV1done')
    expect(wrapper.findComponent({ name: 'SummarizeButton' }).exists()).toBe(true)
    wrapper.unmount()
  })
})
