import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { apiFetchMock } = vi.hoisted(() => ({ apiFetchMock: vi.fn() }))

vi.mock('../../src/lib/apiFetch', () => ({ apiFetch: apiFetchMock }))

import { listSummaryJobs } from '../../src/api/summaryJobs'
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
  content_id: 'BV1hot',
  title: '待学习视频',
  source: 'bilibili',
  up_name: 'UP 主',
  decision_status: 'pending',
  created_at: '2026-07-26T08:00:00Z',
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

describe('follow panels', () => {
  beforeEach(() => apiFetchMock.mockReset())

  it('renders recent summary records and an empty state', async () => {
    apiFetchMock.mockResolvedValue({ success: true, data: [job()] })
    const wrapper = mount(FollowRecordsPanel)
    await flushPromises()

    expect(wrapper.text()).toContain('BV1abc')
    expect(wrapper.text()).toContain('AI 入门')
    expect(wrapper.findComponent({ name: 'SummarizeButton' }).exists()).toBe(true)
    wrapper.unmount()
  })

  it('renders pending hotspots from the hotspots endpoint', async () => {
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
