import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import JobsView from '../../views/JobsView.vue'
import type { Job } from '../../types'

const { mockFetchJobs, mockRunJob, mockPauseJob, mockResumeJob, mockFetchLogs } = vi.hoisted(() => ({
  mockFetchJobs: vi.fn().mockResolvedValue({ data: [] }),
  mockRunJob: vi.fn().mockResolvedValue({ success: true }),
  mockPauseJob: vi.fn().mockResolvedValue({ success: true }),
  mockResumeJob: vi.fn().mockResolvedValue({ success: true }),
  mockFetchLogs: vi.fn().mockResolvedValue({ data: [] }),
}))

vi.mock('../../api/scheduler', () => ({
  fetchJobs: () => mockFetchJobs(),
  runJob: (id: string) => mockRunJob(id),
  pauseJob: (id: string) => mockPauseJob(id),
  resumeJob: (id: string) => mockResumeJob(id),
  fetchLogs: (limit?: number) => mockFetchLogs(limit),
}))

vi.mock('../../composables/useSse', () => ({
  useSse: vi.fn(),
}))

function createJob(overrides: Partial<Job> = {}): Job {
  return {
    id: 'job-1',
    name: 'sync-rss',
    func: 'rss_sync',
    trigger: 'interval',
    next_run_time: '2026-07-15T10:00:00.000Z',
    ...overrides,
  }
}

function mountJobsView(queryClient: QueryClient) {
  return mount(JobsView, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
    },
  })
}

describe('JobsView', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
    mockFetchJobs.mockResolvedValue({ data: [] })
    mockFetchLogs.mockResolvedValue({ data: [] })
    vi.clearAllMocks()
  })

  it('renders title and subtitle', async () => {
    const wrapper = mountJobsView(queryClient)
    await flushPromises()

    expect(wrapper.find('h1').text()).toBe('定时任务')
    expect(wrapper.text()).toContain('同步与摘要的调度状态')
  })

  it('shows loading state while fetching jobs', async () => {
    let resolveFetch: (value: { data: Job[] }) => void = () => {}
    mockFetchJobs.mockImplementationOnce(
      () => new Promise<{ data: Job[] }>((resolve) => {
        resolveFetch = resolve
      }),
    )

    const wrapper = mountJobsView(queryClient)
    await flushPromises()

    expect(wrapper.find('.state-loading').exists()).toBe(true)

    resolveFetch({ data: [] })
    await flushPromises()

    expect(wrapper.find('.state-loading').exists()).toBe(false)
  })

  it('shows error state when fetching jobs fails', async () => {
    mockFetchJobs.mockRejectedValueOnce(new Error('backend down'))

    const wrapper = mountJobsView(queryClient)
    await flushPromises()

    expect(wrapper.find('.state-error').exists()).toBe(true)
    expect(wrapper.find('.state-error').text()).toContain('backend down')
    expect(wrapper.find('.job-list').exists()).toBe(false)
  })

  it('renders JobList with jobs, running state and logs', async () => {
    const job = createJob()
    mockFetchJobs.mockResolvedValue({ data: [job] })

    const wrapper = mountJobsView(queryClient)
    await flushPromises()

    expect(wrapper.text()).toContain('sync-rss')
    expect(wrapper.text()).toContain('interval')
  })

  it('calls runJob when JobList emits run', async () => {
    const job = createJob()
    mockFetchJobs.mockResolvedValue({ data: [job] })

    const wrapper = mountJobsView(queryClient)
    await flushPromises()

    await wrapper.find('button:first-of-type').trigger('click')
    await flushPromises()

    expect(mockRunJob).toHaveBeenCalledWith(job.id)
  })

  it('calls pauseJob when JobList emits pause', async () => {
    const job = createJob()
    mockFetchJobs.mockResolvedValue({ data: [job] })

    const wrapper = mountJobsView(queryClient)
    await flushPromises()

    const buttons = wrapper.findAll('button')
    await buttons[1].trigger('click')
    await flushPromises()

    expect(mockPauseJob).toHaveBeenCalledWith(job.id)
  })

  it('calls resumeJob when JobList emits resume', async () => {
    const job = createJob()
    mockFetchJobs.mockResolvedValue({ data: [job] })

    const wrapper = mountJobsView(queryClient)
    await flushPromises()

    const buttons = wrapper.findAll('button')
    await buttons[2].trigger('click')
    await flushPromises()

    expect(mockResumeJob).toHaveBeenCalledWith(job.id)
  })

  it('reflects running state in JobList while runJob is in flight', async () => {
    let resolveRun: (value: { success: boolean }) => void = () => {}
    mockRunJob.mockImplementationOnce(
      () => new Promise<{ success: boolean }>((resolve) => {
        resolveRun = resolve
      }),
    )
    const job = createJob()
    mockFetchJobs.mockResolvedValue({ data: [job] })

    const wrapper = mountJobsView(queryClient)
    await flushPromises()

    await wrapper.find('button:first-of-type').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('执行中')

    resolveRun({ success: true })
    await flushPromises()

    expect(wrapper.text()).not.toContain('执行中')
  })

  it('fetches logs with default limit', async () => {
    mountJobsView(queryClient)
    await flushPromises()

    expect(mockFetchLogs).toHaveBeenCalledWith(20)
  })
})
