import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import InputView from '../InputView.vue'

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }))
vi.mock('@tauri-apps/api/event', () => ({ listen: vi.fn(() => vi.fn()) }))

import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'

import type { Event, EventName } from '@tauri-apps/api/event'

type EventCallback = (event: Event<unknown>) => void

function buildEvent<T>(eventName: EventName, payload: T): Event<T> {
  return { event: eventName, id: 0, payload }
}

describe('InputView', () => {
  let eventCallbacks: Record<string, EventCallback> = {}
  let unlistenMocks: ReturnType<typeof vi.fn>[] = []

  beforeEach(() => {
    vi.resetAllMocks()
    eventCallbacks = {}
    unlistenMocks = []
    vi.mocked(listen).mockImplementation((eventName: string, callback: EventCallback) => {
      eventCallbacks[eventName] = callback
      const unlisten = vi.fn()
      unlistenMocks.push(unlisten)
      return Promise.resolve(unlisten)
    })
  })

  afterEach(() => {
    unlistenMocks.forEach((unlisten) => {
      expect(unlisten).toHaveBeenCalled()
    })
  })

  it('initial state: input is empty, submit button is disabled, no message shown', () => {
    const wrapper = mount(InputView)

    const input = wrapper.find('input')
    const button = wrapper.find('button')

    expect((input.element as HTMLInputElement).value).toBe('')
    expect(button.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.message').exists()).toBe(false)

    wrapper.unmount()
  })

  it('typing a URL enables the submit button', async () => {
    const wrapper = mount(InputView)

    const input = wrapper.find('input')
    await input.setValue('https://example.com')
    await flushPromises()

    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  it('clicking submit invokes submit_url and shows the queued message', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce(undefined)

    const wrapper = mount(InputView)
    const input = wrapper.find('input')
    await input.setValue('https://example.com')
    await flushPromises()

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(mockedInvoke).toHaveBeenCalledWith('submit_url', {
      url: 'https://example.com',
      source: 'menubar',
    })
    expect(wrapper.find('.message').text()).toBe('已加入处理队列')

    wrapper.unmount()
  })

  it('simulating task_progress shows the progress bar and message', async () => {
    const wrapper = mount(InputView)
    await flushPromises()

    eventCallbacks['task_progress'](
      buildEvent('task_progress', {
        task_id: 'task-1',
        status: 'running',
        progress_pct: 45,
        message: '下载中...',
      }),
    )
    await flushPromises()

    const progressBar = wrapper.find('.progress-bar')
    expect(progressBar.exists()).toBe(true)
    expect(progressBar.attributes('style')).toContain('width: 45%')
    expect(wrapper.find('.progress-text').text()).toBe('下载中...')

    wrapper.unmount()
  })

  it('simulating task_complete success shows the completion message', async () => {
    const wrapper = mount(InputView)
    await flushPromises()

    eventCallbacks['task_complete'](
      buildEvent('task_complete', {
        task_id: 'task-1',
        status: 'success',
        result: { url: 'https://example.com', title: 'Example Title' },
      }),
    )
    await flushPromises()

    expect(wrapper.find('.message').text()).toBe('完成: Example Title')
    expect(wrapper.find('.progress').exists()).toBe(false)

    wrapper.unmount()
  })

  it('pressing Escape invokes hide_window', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce(undefined)

    const wrapper = mount(InputView)
    await flushPromises()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()

    expect(mockedInvoke).toHaveBeenCalledWith('hide_window', { label: 'input' })

    wrapper.unmount()
  })

  it('clicking footer buttons invokes corresponding window commands', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValue(undefined)

    const wrapper = mount(InputView)
    await flushPromises()

    const footerButtons = wrapper.findAll('.footer button')
    expect(footerButtons).toHaveLength(3)

    await footerButtons[0].trigger('click')
    await footerButtons[1].trigger('click')
    await footerButtons[2].trigger('click')
    await flushPromises()

    expect(mockedInvoke).toHaveBeenCalledWith('open_tasks_window')
    expect(mockedInvoke).toHaveBeenCalledWith('open_settings_window')
    expect(mockedInvoke).toHaveBeenCalledWith('open_obsidian')

    wrapper.unmount()
  })

  it('renders an input field with the input-field class', async () => {
    const wrapper = mount(InputView)
    await flushPromises()

    try {
      expect(wrapper.find('.input-field').exists()).toBe(true)
    } finally {
      wrapper.unmount()
    }
  })
})
