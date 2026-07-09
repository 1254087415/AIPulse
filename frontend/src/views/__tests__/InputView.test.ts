import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import InputView from '../InputView.vue'
import { invoke } from '@tauri-apps/api/core'

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

describe('InputView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetListeners()
    vi.mocked(invoke).mockResolvedValue(undefined)
  })

  it('renders a large centered input with the placeholder', () => {
    const wrapper = mount(InputView)
    const input = wrapper.find('.input-field')

    expect(input.exists()).toBe(true)
    expect(input.attributes('placeholder')).toBe('粘贴 RSS / 视频 / 文章链接')
    expect(wrapper.find('.status-hint').text()).toBe('粘贴链接，开始处理')
    wrapper.unmount()
  })

  it('disables the submit button when the input is empty', () => {
    const wrapper = mount(InputView)
    const button = wrapper.find('.submit-button')

    expect(button.element.disabled).toBe(true)
    wrapper.unmount()
  })

  it('enables the submit button after typing a URL', async () => {
    const wrapper = mount(InputView)
    const input = wrapper.find('.input-field')

    await input.setValue('https://example.com/article')
    const button = wrapper.find('.submit-button')

    expect(button.element.disabled).toBe(false)
    wrapper.unmount()
  })

  it('submits the URL when pressing Enter in the input', async () => {
    const wrapper = mount(InputView)
    const input = wrapper.find('.input-field')

    await input.setValue('https://example.com/article')
    await input.trigger('keydown.enter')
    await flushPromises()

    expect(invoke).toHaveBeenCalledWith('submit_url', {
      url: 'https://example.com/article',
      source: 'menubar',
    })
    wrapper.unmount()
  })

  it('submits the URL when clicking the submit button', async () => {
    const wrapper = mount(InputView)
    const input = wrapper.find('.input-field')

    await input.setValue('https://example.com/article')
    await wrapper.find('.submit-button').trigger('click')
    await flushPromises()

    expect(invoke).toHaveBeenCalledWith('submit_url', {
      url: 'https://example.com/article',
      source: 'menubar',
    })
    wrapper.unmount()
  })

  it('clears the input after a successful submit', async () => {
    const wrapper = mount(InputView)
    const input = wrapper.find('.input-field')

    await input.setValue('https://example.com/article')
    await wrapper.find('.submit-button').trigger('click')
    await flushPromises()

    expect(input.element.value).toBe('')
    wrapper.unmount()
  })

  it('shows a submitting state while the URL is being submitted', async () => {
    let resolveSubmit: (value: unknown) => void = () => {}
    vi.mocked(invoke).mockImplementation(
      () => new Promise((resolve) => (resolveSubmit = resolve)),
    )

    const wrapper = mount(InputView, { attachTo: document.body })
    const input = wrapper.find('.input-field')

    await input.setValue('https://example.com/article')
    const button = wrapper.find('.submit-button')
    await button.trigger('click')
    await flushPromises()

    expect(button.element.disabled).toBe(true)
    expect(button.text()).toBe('提交中...')

    resolveSubmit(undefined)
    await flushPromises()

    expect(button.text()).toBe('开始处理')
    wrapper.unmount()
  })

  it('displays an error message when submission fails', async () => {
    vi.mocked(invoke).mockRejectedValue(new Error('network error'))

    const wrapper = mount(InputView)
    const input = wrapper.find('.input-field')

    await input.setValue('https://example.com/article')
    await wrapper.find('.submit-button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.status-message').text()).toContain('提交失败')
    wrapper.unmount()
  })

  it('hides the window when Escape is pressed', async () => {
    const wrapper = mount(InputView)
    await flushPromises()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()

    expect(invoke).toHaveBeenCalledWith('hide_window', { label: 'input' })
    wrapper.unmount()
  })

  it('shows the progress bar and text while processing', async () => {
    const wrapper = mount(InputView)
    await flushPromises()

    emit('task_progress', {
      task_id: 'task-1',
      status: 'running',
      progress_pct: 45,
      message: '提取中...',
    })
    await flushPromises()

    const bar = wrapper.find('.progress-bar')
    expect(bar.exists()).toBe(true)
    expect(bar.attributes('style')).toContain('width: 45%')
    expect(wrapper.find('.progress-text').text()).toBe('提取中...')
    wrapper.unmount()
  })

  it('clears the progress bar after task completion', async () => {
    const wrapper = mount(InputView)
    await flushPromises()

    emit('task_progress', {
      task_id: 'task-1',
      status: 'running',
      progress_pct: 50,
      message: '提取中...',
    })
    await flushPromises()

    emit('task_complete', {
      task_id: 'task-1',
      status: 'success',
      result: { title: '完成的文章' },
    })
    await flushPromises()

    expect(wrapper.find('.progress-bar').exists()).toBe(false)
    wrapper.unmount()
  })

  it('adds incoming tasks to the recent tasks preview', async () => {
    const wrapper = mount(InputView)
    await flushPromises()

    emit('task_progress', {
      task_id: 'task-1',
      status: 'running',
      url: 'https://example.com/1',
      title: '文章一',
    })
    await flushPromises()

    const tasks = wrapper.findAll('.recent-task')
    expect(tasks.length).toBe(1)
    expect(tasks[0].text()).toContain('文章一')
    expect(tasks[0].find('.status-dot').exists()).toBe(true)
    wrapper.unmount()
  })

  it('updates an existing recent task instead of duplicating it', async () => {
    const wrapper = mount(InputView)
    await flushPromises()

    emit('task_progress', {
      task_id: 'task-1',
      status: 'running',
      url: 'https://example.com/1',
      title: '文章一',
    })
    emit('task_progress', {
      task_id: 'task-1',
      status: 'completed',
      url: 'https://example.com/1',
      title: '文章一',
    })
    await flushPromises()

    const tasks = wrapper.findAll('.recent-task')
    expect(tasks.length).toBe(1)
    expect(tasks[0].find('.status-dot.completed').exists()).toBe(true)
    wrapper.unmount()
  })

  it('keeps only the three most recent tasks', async () => {
    const wrapper = mount(InputView)
    await flushPromises()

    for (let i = 1; i <= 4; i++) {
      emit('task_progress', {
        task_id: `task-${i}`,
        status: 'running',
        url: `https://example.com/${i}`,
        title: `文章 ${i}`,
      })
    }
    await flushPromises()

    const tasks = wrapper.findAll('.recent-task')
    expect(tasks.length).toBe(3)
    expect(tasks[0].text()).toContain('文章 4')
    expect(tasks[2].text()).toContain('文章 2')
    wrapper.unmount()
  })

  it('shows an empty state when there are no recent tasks', () => {
    const wrapper = mount(InputView)

    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.find('.empty-state').text()).toContain('还没有处理记录')
    wrapper.unmount()
  })

  it('focuses the input on mount', () => {
    const wrapper = mount(InputView, { attachTo: document.body })
    const input = wrapper.find('.input-field')

    expect(input.element).toBe(document.activeElement)
    wrapper.unmount()
  })
})
