/**
 * SettingsView · obsidian vault picker integration (spec E5).
 *
 * - window.showDirectoryPicker() preferred when available
 * - falls back to <input type="file" webkitdirectory> otherwise
 * - selected path triggers PATCH /api/settings and is reflected in UI
 *
 * Implementation mocks live in this file (vi.stubGlobal / vi.fn) so the
 * production component does not need to know it is being driven by tests.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

import SettingsView from '../SettingsView.vue'

// Stub the settings API so we can capture the PATCH payload.
const patchSpy = vi.fn()
vi.mock('../../../src/api/settings', () => ({
  getSettings: vi.fn(async () => ({
    kimi: { kimi_api_key: '', kimi_base_url: '', kimi_model: '', learning_notification_enabled: true },
    obsidian: { obsidian_vault_path: '', obsidian_archive_folder: 'AIPulse' },
    wechat: { wechat_appid: '', wechat_appsecret: '', wechat_template_id: '', wechat_openid: '' },
    feishu: { feishu_webhook_url: '', feishu_secret: '' },
  })),
  patchSettings: (...args: unknown[]) => {
    patchSpy(...args)
    return Promise.resolve({
      kimi: { kimi_api_key: '', kimi_base_url: '', kimi_model: '', learning_notification_enabled: true },
      obsidian: { obsidian_vault_path: '', obsidian_archive_folder: 'AIPulse' },
      wechat: { wechat_appid: '', wechat_appsecret: '', wechat_template_id: '', wechat_openid: '' },
      feishu: { feishu_webhook_url: '', feishu_secret: '' },
    })
  },
}))

interface MockFileSystemDirectoryHandle {
  kind: 'directory'
  name: string
}

async function expandObsidianPanel(wrapper: ReturnType<typeof mount>) {
  const header = wrapper.find('[data-testid="panel-obsidian-header"]')
  if (header.exists()) {
    await header.trigger('click')
    await flushPromises()
  }
}

describe('SettingsView · obsidian vault picker', () => {
  beforeEach(() => {
    patchSpy.mockClear()
  })

  afterEach(() => {
    // Reset any global stubs we installed in tests.
    delete (window as unknown as { showDirectoryPicker?: unknown }).showDirectoryPicker
    vi.restoreAllMocks()
  })

  it('renders a "选择目录" button in the obsidian panel (E5 #1)', async () => {
    const wrapper = mount(SettingsView)
    await expandObsidianPanel(wrapper)

    const picker = wrapper.find('[data-testid="pick-obsidian-vault"]')
    expect(picker.exists()).toBe(true)
  })

  it('uses window.showDirectoryPicker when available and posts the picked path (E5 #1 + #3 + #4)', async () => {
    const dirHandle: MockFileSystemDirectoryHandle = { kind: 'directory', name: 'MyVault' }
    const showPicker = vi.fn(async () => dirHandle)
    ;(window as unknown as { showDirectoryPicker?: unknown }).showDirectoryPicker = showPicker

    const wrapper = mount(SettingsView)
    await flushPromises()
    await expandObsidianPanel(wrapper)

    await wrapper.find('[data-testid="pick-obsidian-vault"]').trigger('click')
    await flushPromises()

    expect(showPicker).toHaveBeenCalledTimes(1)

    // The picked directory name must surface in the bound input.
    const input = wrapper.find<HTMLInputElement>('#obsidian-vault-path')
    expect((input.element as HTMLInputElement).value).toContain('MyVault')

    wrapper.unmount()
  })

  it('falls back to <input type="file" webkitdirectory> when showDirectoryPicker is missing (E5 #2)', async () => {
    // No window.showDirectoryPicker present.
    expect((window as unknown as { showDirectoryPicker?: unknown }).showDirectoryPicker).toBeUndefined()

    const wrapper = mount(SettingsView)
    await flushPromises()
    await expandObsidianPanel(wrapper)

    // Clicking the picker button should create + click + remove a hidden
    // <input type="file" webkitdirectory>. We instrument the DOM via a spy
    // on document.body.appendChild / removeChild.
    const appendSpy = vi.spyOn(document.body, 'appendChild')
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click')

    await wrapper.find('[data-testid="pick-obsidian-vault"]').trigger('click')
    await flushPromises()

    expect(appendSpy).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()

    appendSpy.mockRestore()
    clickSpy.mockRestore()
    wrapper.unmount()
  })

  it('submits PATCH /api/settings with the picked path (E5 #3)', async () => {
    const dirHandle: MockFileSystemDirectoryHandle = { kind: 'directory', name: 'ChosenVault' }
    ;(window as unknown as { showDirectoryPicker?: unknown }).showDirectoryPicker = vi.fn(async () => dirHandle)

    const wrapper = mount(SettingsView)
    await flushPromises()
    await expandObsidianPanel(wrapper)

    await wrapper.find('[data-testid="pick-obsidian-vault"]').trigger('click')
    await flushPromises()

    // Save the form (the picker should already populate the input).
    const form = wrapper.find('form.settings-form')
    expect(form.exists()).toBe(true)
    await form.trigger('submit.prevent')
    await flushPromises()

    expect(patchSpy).toHaveBeenCalledTimes(1)
    const payload = patchSpy.mock.calls[0][0] as { obsidian_vault_path?: string }
    expect(payload.obsidian_vault_path ?? '').toContain('ChosenVault')

    wrapper.unmount()
  })

  it('shows a confirmation when the picker succeeds (E5 #4)', async () => {
    const dirHandle: MockFileSystemDirectoryHandle = { kind: 'directory', name: 'ConfirmedVault' }
    ;(window as unknown as { showDirectoryPicker?: unknown }).showDirectoryPicker = vi.fn(async () => dirHandle)

    const wrapper = mount(SettingsView)
    await flushPromises()
    await expandObsidianPanel(wrapper)

    await wrapper.find('[data-testid="pick-obsidian-vault"]').trigger('click')
    await nextTick()
    await flushPromises()

    // The success indicator uses data-testid="vault-picker-status" and reads
    // "已选择：<name>" once the picker resolves.
    const status = wrapper.find('[data-testid="vault-picker-status"]')
    expect(status.exists()).toBe(true)
    expect(status.text()).toContain('ConfirmedVault')

    wrapper.unmount()
  })

  it('still renders the manual text input as a fallback so the user can paste (E5 #4)', async () => {
    const wrapper = mount(SettingsView)
    await flushPromises()
    await expandObsidianPanel(wrapper)

    const input = wrapper.find('#obsidian-vault-path')
    expect(input.exists()).toBe(true)
    expect(input.attributes('type')).toBe('text')

    wrapper.unmount()
  })
})