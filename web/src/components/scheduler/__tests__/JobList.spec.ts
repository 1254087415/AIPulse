import { describe, expect, it } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import JobList from '../JobList.vue'
import type { Job } from '../../../types'
import type { SchedulerLog } from '../../../api/scheduler'

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

function createLog(overrides: Partial<SchedulerLog> = {}): SchedulerLog {
  return {
    id: 'log-1',
    job_id: 'job-1',
    job_name: 'sync-rss',
    status: 'success',
    started_at: '2026-07-15T09:00:00.000Z',
    finished_at: '2026-07-15T09:01:00.000Z',
    message: 'completed',
    exception: null,
    ...overrides,
  }
}

function mountJobList(props: { jobs?: Job[]; running?: Record<string, boolean>; logs?: SchedulerLog[] } = {}) {
  return mount(JobList, {
    props: {
      jobs: [],
      running: {},
      ...props,
    },
  })
}

describe('JobList', () => {
  it('renders empty job list without crashing', () => {
    const wrapper = mountJobList()

    expect(wrapper.findAll('li').length).toBe(0)
    expect(wrapper.find('.log-section').exists()).toBe(false)
  })

  it('renders job name, trigger and next run time', () => {
    const wrapper = mountJobList({ jobs: [createJob()] })

    expect(wrapper.text()).toContain('sync-rss')
    expect(wrapper.text()).toContain('interval')
    expect(wrapper.text()).toContain('下次运行')
  })

  it('formats next_run_time as zh-CN locale string', () => {
    const wrapper = mountJobList({ jobs: [createJob({ next_run_time: '2026-07-15T10:00:00.000Z' })] })

    expect(wrapper.find('.job-next').text()).toContain('2026')
    expect(wrapper.find('.job-next').text()).toContain('7')
  })

  it('shows "无" when next_run_time is null', () => {
    const wrapper = mountJobList({ jobs: [createJob({ next_run_time: null })] })

    expect(wrapper.find('.job-next').text()).toContain('无')
  })

  it('emits run event with job id', async () => {
    const wrapper = mountJobList({ jobs: [createJob()] })

    await wrapper.find('button:first-of-type').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('run')).toHaveLength(1)
    expect(wrapper.emitted('run')![0]).toEqual(['job-1'])
  })

  it('emits pause event with job id', async () => {
    const wrapper = mountJobList({ jobs: [createJob()] })

    const buttons = wrapper.findAll('button')
    await buttons[1].trigger('click')
    await flushPromises()

    expect(wrapper.emitted('pause')).toHaveLength(1)
    expect(wrapper.emitted('pause')![0]).toEqual(['job-1'])
  })

  it('emits resume event with job id', async () => {
    const wrapper = mountJobList({ jobs: [createJob()] })

    const buttons = wrapper.findAll('button')
    await buttons[2].trigger('click')
    await flushPromises()

    expect(wrapper.emitted('resume')).toHaveLength(1)
    expect(wrapper.emitted('resume')![0]).toEqual(['job-1'])
  })

  it('disables run button and shows running text when job is running', () => {
    const wrapper = mountJobList({ jobs: [createJob()], running: { 'job-1': true } })

    const runButton = wrapper.find('button:first-of-type')
    expect(runButton.text()).toContain('执行中')
    expect((runButton.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('renders log section when logs are provided', () => {
    const wrapper = mountJobList({ logs: [createLog()] })

    expect(wrapper.find('.log-section').exists()).toBe(true)
    expect(wrapper.findAll('.log-item').length).toBe(1)
  })

  it('renders log exception when present', () => {
    const wrapper = mountJobList({ logs: [createLog({ exception: 'connection timeout' })] })

    expect(wrapper.find('.log-exception').exists()).toBe(true)
    expect(wrapper.text()).toContain('connection timeout')
  })

  it('applies error styling to failed logs', () => {
    const wrapper = mountJobList({ logs: [createLog({ status: 'error' })] })

    expect(wrapper.find('.log-error').exists()).toBe(true)
  })

  it('shows "无" for log finished_at when null', () => {
    const wrapper = mountJobList({ logs: [createLog({ finished_at: null })] })

    expect(wrapper.find('.log-time').text()).toBe('无')
  })
})
