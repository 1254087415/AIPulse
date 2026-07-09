import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import TasksView from '../TasksView.vue'

const { listeners, emit, resetListeners } = vi.hoisted(() => {
  const listeners = new Map<string, Array<(payload: unknown) => void>>()
  return {
    listeners,
    emit: (event: string, payload: unknown) => {
      listeners.get(event)?.forEach((cb) => cb(payload))
    },
    resetListeners: () => listeners.clear(),
  }
})

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }))
vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn((event: string, cb: (event: { payload: unknown }) => void) => {
    if (!listeners.has(event)) {
      listeners.set(event, [])
    }
    const cbs = listeners.get(event)!
    const wrapped = (payload: unknown) => cb({ payload })
    cbs.push(wrapped)
    return Promise.resolve(
      vi.fn(() => {
        const index = cbs.indexOf(wrapped)
        if (index >= 0) cbs.splice(index, 1)
      }),
    )
  }),
}))

import { invoke } from '@tauri-apps/api/core'

const createTestRouter = () =>
  createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', redirect: '/input' },
      { path: '/input', component: { template: '<div>Input</div>' } },
      { path: '/tasks', component: { template: '<div>Tasks</div>' } },
      { path: '/settings', component: { template: '<div>Settings</div>' } },
    ],
  })

describe('TasksView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetListeners()
    vi.mocked(invoke).mockResolvedValue({ tasks: [] })
  })

  it('calls list_tasks with limit 50 on mount', async () => {
    mount(TasksView, {
      global: { plugins: [createTestRouter()] },
    })
    await flushPromises()

    expect(invoke).toHaveBeenCalledWith('list_tasks', { limit: 50 })
  })

  it('renders empty state when there are no tasks', async () => {
    const wrapper = mount(TasksView, {
      global: { plugins: [createTestRouter()] },
    })
    await flushPromises()

    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.text()).toContain('还没有任务')
    expect(wrapper.text()).toContain('去输入页粘贴一个链接开始')
    expect(wrapper.find('.empty-state .empty-logo').exists()).toBe(true)

    wrapper.unmount()
  })

  it('renders task cards with status dots and labels', async () => {
    vi.mocked(invoke).mockResolvedValue({
      tasks: [
        { id: 'task-1', url: 'https://example.com/1', status: 'running', title: 'Running Task' },
        { id: 'task-2', url: 'https://example.com/2', status: 'completed', title: 'Completed Task' },
        { id: 'task-3', url: 'https://example.com/3', status: 'failed', title: 'Failed Task' },
        { id: 'task-4', url: 'https://example.com/4', status: 'pending', title: 'Pending Task' },
      ],
    })

    const wrapper = mount(TasksView, {
      global: { plugins: [createTestRouter()] },
    })
    await flushPromises()

    const cards = wrapper.findAll('.task-card')
    expect(cards).toHaveLength(4)

    expect(cards[0].find('.status-dot.running').exists()).toBe(true)
    expect(cards[0].text()).toContain('RUNNING')
    expect(cards[0].text()).toContain('Running Task')

    expect(cards[1].find('.status-dot.completed').exists()).toBe(true)
    expect(cards[1].text()).toContain('DONE')

    expect(cards[2].find('.status-dot.failed').exists()).toBe(true)
    expect(cards[2].text()).toContain('FAILED')

    expect(cards[3].find('.status-dot.pending').exists()).toBe(true)
    expect(cards[3].text()).toContain('PENDING')

    wrapper.unmount()
  })

  it('shows the task source URL in mono font', async () => {
    vi.mocked(invoke).mockResolvedValue({
      tasks: [
        { id: 'task-1', url: 'https://example.com/path/article', status: 'running', title: 'Article' },
      ],
    })

    const wrapper = mount(TasksView, {
      global: { plugins: [createTestRouter()] },
    })
    await flushPromises()

    const source = wrapper.find('.task-source')
    expect(source.exists()).toBe(true)
    expect(source.text()).toBe('example.com')

    wrapper.unmount()
  })

  it('shows a retry button for failed tasks that invokes retry_task', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({
      tasks: [{ id: 'task-1', url: 'https://example.com', status: 'failed', title: 'Failed Task' }],
    })
    mockedInvoke.mockResolvedValueOnce(undefined)

    const wrapper = mount(TasksView, {
      global: { plugins: [createTestRouter()] },
    })
    await flushPromises()

    const retryButton = wrapper.find('.task-card.failed .retry-button')
    expect(retryButton.exists()).toBe(true)
    expect(retryButton.text()).toBe('重试')

    await retryButton.trigger('click')
    await flushPromises()

    expect(mockedInvoke).toHaveBeenLastCalledWith('retry_task', { task_id: 'task-1' })

    wrapper.unmount()
  })

  it('adds new tasks from task_progress events', async () => {
    const wrapper = mount(TasksView, {
      global: { plugins: [createTestRouter()] },
    })
    await flushPromises()

    emit('task_progress', {
      task_id: 'task-1',
      status: 'running',
      url: 'https://example.com/1',
      title: 'New Task',
    })
    await flushPromises()

    const cards = wrapper.findAll('.task-card')
    expect(cards).toHaveLength(1)
    expect(cards[0].text()).toContain('New Task')
    expect(cards[0].find('.status-dot.running').exists()).toBe(true)

    wrapper.unmount()
  })

  it('updates an existing task when a task_progress event arrives', async () => {
    vi.mocked(invoke).mockResolvedValue({
      tasks: [{ id: 'task-1', url: 'https://example.com', status: 'running', title: 'Task' }],
    })

    const wrapper = mount(TasksView, {
      global: { plugins: [createTestRouter()] },
    })
    await flushPromises()

    emit('task_progress', {
      task_id: 'task-1',
      status: 'completed',
      url: 'https://example.com',
      title: 'Task',
    })
    await flushPromises()

    const card = wrapper.find('.task-card')
    expect(card.find('.status-dot.completed').exists()).toBe(true)
    expect(card.text()).toContain('DONE')

    wrapper.unmount()
  })

  it('displays an error banner when loading tasks fails', async () => {
    vi.mocked(invoke).mockRejectedValue(new Error('network error'))

    const wrapper = mount(TasksView, {
      global: { plugins: [createTestRouter()] },
    })
    await flushPromises()

    expect(wrapper.find('.error-banner').exists()).toBe(true)
    expect(wrapper.text()).toContain('加载任务失败')

    wrapper.unmount()
  })

  it('displays an error banner when retry fails', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({
      tasks: [{ id: 'task-1', url: 'https://example.com', status: 'failed', title: 'Failed Task' }],
    })
    mockedInvoke.mockRejectedValueOnce(new Error('retry error'))

    const wrapper = mount(TasksView, {
      global: { plugins: [createTestRouter()] },
    })
    await flushPromises()

    await wrapper.find('.task-card.failed .retry-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.error-banner').exists()).toBe(true)
    expect(wrapper.text()).toContain('重试失败')

    wrapper.unmount()
  })

  it('cleans up the event listener on unmount', async () => {
    const wrapper = mount(TasksView, {
      global: { plugins: [createTestRouter()] },
    })
    await flushPromises()

    wrapper.unmount()

    expect(listeners.get('task_progress')?.length ?? 0).toBe(0)
  })
})
