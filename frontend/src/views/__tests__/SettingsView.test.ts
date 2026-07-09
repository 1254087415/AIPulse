import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SettingsView from '../SettingsView.vue'

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }))

import { invoke } from '@tauri-apps/api/core'

describe('SettingsView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('loads settings on mount and renders returned values alongside defaults', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({
      obsidian_vault_path: '/path/to/vault',
      llm_model: 'custom-model',
    })

    const wrapper = mount(SettingsView)
    await flushPromises()

    expect(mockedInvoke).toHaveBeenCalledWith('get_settings')
    expect((wrapper.find('#obsidian-vault-path').element as HTMLInputElement).value).toBe(
      '/path/to/vault',
    )
    expect((wrapper.find('#llm-model').element as HTMLInputElement).value).toBe('custom-model')
    expect((wrapper.find('#obsidian-archive-folder').element as HTMLInputElement).value).toBe(
      'AIPulse',
    )

    wrapper.unmount()
  })

  it('renders all setting sections inside collapsible panels', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({})

    const wrapper = mount(SettingsView)
    await flushPromises()

    expect(wrapper.text()).toContain('Kimi Code LLM')
    expect(wrapper.text()).toContain('Obsidian')
    expect(wrapper.text()).toContain('飞书推送')
    expect(wrapper.text()).toContain('微信推送')

    wrapper.unmount()
  })

  it('expands the Kimi Code LLM panel by default and collapses the others', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({})

    const wrapper = mount(SettingsView)
    await flushPromises()

    expect(wrapper.find('[data-testid="panel-llm"]').classes()).toContain('is-expanded')
    expect(wrapper.find('[data-testid="panel-obsidian"]').classes()).not.toContain('is-expanded')
    expect(wrapper.find('[data-testid="panel-feishu"]').classes()).not.toContain('is-expanded')
    expect(wrapper.find('[data-testid="panel-wechat"]').classes()).not.toContain('is-expanded')

    wrapper.unmount()
  })

  it('toggles panel expand and collapse on header click', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({})

    const wrapper = mount(SettingsView)
    await flushPromises()

    const obsidianHeader = wrapper.find('[data-testid="panel-obsidian-header"]')
    await obsidianHeader.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="panel-obsidian"]').classes()).toContain('is-expanded')

    await obsidianHeader.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="panel-obsidian"]').classes()).not.toContain('is-expanded')

    wrapper.unmount()
  })

  it('toggles password visibility for secret fields', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({})

    const wrapper = mount(SettingsView)
    await flushPromises()

    const apiKeyInput = wrapper.find('#llm-api-key')
    expect(apiKeyInput.attributes('type')).toBe('password')

    const toggle = wrapper.find('[data-testid="toggle-llm-api-key"]')
    await toggle.trigger('click')
    await flushPromises()

    expect(wrapper.find('#llm-api-key').attributes('type')).toBe('text')

    await toggle.trigger('click')
    await flushPromises()

    expect(wrapper.find('#llm-api-key').attributes('type')).toBe('password')

    wrapper.unmount()
  })

  it('clicking save invokes update_settings with the changed settings', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({})
    mockedInvoke.mockResolvedValueOnce({})

    const wrapper = mount(SettingsView)
    await flushPromises()

    const apiKeyInput = wrapper.find('#llm-api-key')
    await apiKeyInput.setValue('sk-test')
    await flushPromises()

    await wrapper.find('[data-testid="save-button"]').trigger('click')
    await flushPromises()

    expect(mockedInvoke).toHaveBeenLastCalledWith('update_settings', {
      settings: expect.objectContaining({ llm_api_key: 'sk-test' }),
    })

    wrapper.unmount()
  })

  it('shows saving and saved states on successful save', async () => {
    const mockedInvoke = vi.mocked(invoke)
    let resolveUpdate: ((value: unknown) => void) | undefined
    const updatePromise = new Promise((resolve) => {
      resolveUpdate = resolve
    })
    mockedInvoke.mockResolvedValueOnce({})
    mockedInvoke.mockReturnValueOnce(updatePromise)

    const wrapper = mount(SettingsView)
    await flushPromises()

    const saveButton = wrapper.find('[data-testid="save-button"]')
    const clickPromise = saveButton.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('保存中...')

    resolveUpdate?.({})
    await clickPromise
    await flushPromises()

    expect(wrapper.text()).toContain('已保存')

    wrapper.unmount()
  })

  it('shows an error message below the button when saving fails', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({})
    mockedInvoke.mockRejectedValueOnce(new Error('network error'))

    const wrapper = mount(SettingsView)
    await flushPromises()

    await wrapper.find('[data-testid="save-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="save-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('保存失败')

    wrapper.unmount()
  })

  it('merges returned settings from update_settings into the form', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({})
    mockedInvoke.mockResolvedValueOnce({
      llm_base_url: 'https://updated.example.com',
      llm_model: 'updated-model',
    })

    const wrapper = mount(SettingsView)
    await flushPromises()

    await wrapper.find('[data-testid="save-button"]').trigger('click')
    await flushPromises()

    expect((wrapper.find('#llm-base-url').element as HTMLInputElement).value).toBe(
      'https://updated.example.com',
    )
    expect((wrapper.find('#llm-model').element as HTMLInputElement).value).toBe('updated-model')

    wrapper.unmount()
  })

  it('skips fields containing masked secrets when saving', async () => {
    const mockedInvoke = vi.mocked(invoke)
    mockedInvoke.mockResolvedValueOnce({
      llm_api_key: 'sk-***masked***',
      feishu_secret: '***',
    })
    mockedInvoke.mockResolvedValueOnce({})

    const wrapper = mount(SettingsView)
    await flushPromises()

    await wrapper.find('[data-testid="save-button"]').trigger('click')
    await flushPromises()

    expect(mockedInvoke).toHaveBeenLastCalledWith(
      'update_settings',
      {
        settings: expect.not.objectContaining({
          llm_api_key: 'sk-***masked***',
          feishu_secret: '***',
        }),
      },
    )

    wrapper.unmount()
  })
})
