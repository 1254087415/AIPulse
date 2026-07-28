/**
 * SettingsView — HTTP variant (spec §10.1 + CLAUDE.md §4).
 *
 * Settings must:
 *  - Load via GET /api/settings (nested `{kimi, obsidian, wechat, feishu}`)
 *  - Render flat inputs that match the v0.3 settings schema
 *  - Round-trip masked secrets safely (skip them on save)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { getSettingsMock, patchSettingsMock } = vi.hoisted(() => ({
  getSettingsMock: vi.fn(),
  patchSettingsMock: vi.fn(),
}))

vi.mock('../../src/api/settings', () => ({
  getSettings: () => getSettingsMock(),
  patchSettings: (...args: unknown[]) => patchSettingsMock(...args),
}))

import SettingsView from '../../src/views/SettingsView.vue'

const groupedResponse = {
  llm: {
    llm_api_key: 'sk-***49VK',
    llm_base_url: 'https://api.minimaxi.com/v1',
    llm_model: 'MiniMax-M2.5',
    learning_notification_enabled: true,
  },
  obsidian: {
    obsidian_vault_path: '/Users/zab/Documents/Obsidian Vault',
    obsidian_archive_folder: 'AIPulse',
  },
  wechat: {
    wechat_appid: '',
    wechat_appsecret: '',
    wechat_template_id: '',
    wechat_openid: '',
  },
  feishu: {
    feishu_webhook_url: '',
    feishu_secret: '',
  },
  api_auth: {
    aipulse_api_token: '',
  },
}

async function mountView() {
  const wrapper = mount(SettingsView)
  await flushPromises()
  return wrapper
}

async function submitForm(wrapper: ReturnType<typeof mount>): Promise<void> {
  const form = wrapper.find('form.settings-form')
  await form.trigger('submit.prevent')
  await flushPromises()
}

describe('SettingsView (HTTP)', () => {
  beforeEach(() => {
    getSettingsMock.mockReset()
    patchSettingsMock.mockReset()
    getSettingsMock.mockResolvedValue(groupedResponse)
    patchSettingsMock.mockResolvedValue(groupedResponse)
  })

  it('loads settings via HTTP GET /api/settings, not via Tauri invoke', async () => {
    const wrapper = await mountView()
    expect(getSettingsMock).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-testid="load-error"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('renders the obsidian vault path from the real response', async () => {
    const wrapper = await mountView()
    const input = wrapper.find('#obsidian-vault-path').element as HTMLInputElement
    expect(input.value).toBe('/Users/zab/Documents/Obsidian Vault')
    wrapper.unmount()
  })

  it('renders masked secrets as their masked form (does not expose the raw value)', async () => {
    const wrapper = await mountView()
    const apiKey = wrapper.find('#llm-api-key').element as HTMLInputElement
    expect(apiKey.value).toBe('sk-***49VK')
    wrapper.unmount()
  })

  it('does not send masked secrets on save (they would otherwise overwrite the real value)', async () => {
    const wrapper = await mountView()
    await submitForm(wrapper)

    expect(patchSettingsMock).toHaveBeenCalledTimes(1)
    const payload = patchSettingsMock.mock.calls[0][0] as Record<string, unknown>
    expect(payload).not.toHaveProperty('llm_api_key')
    expect(payload).not.toHaveProperty('feishu_secret')
    expect(payload).not.toHaveProperty('wechat_appsecret')

    wrapper.unmount()
  })

  it('sends a non-masked secret when the user types a new value', async () => {
    const wrapper = await mountView()
    await wrapper.find('[data-testid="toggle-llm-api-key"]').trigger('click')
    await flushPromises()
    await wrapper.find('#llm-api-key').setValue('sk-new-secret-value-1234')
    await flushPromises()
    await submitForm(wrapper)

    const payload = patchSettingsMock.mock.calls[0][0] as Record<string, unknown>
    expect(payload.llm_api_key).toBe('sk-new-secret-value-1234')

    wrapper.unmount()
  })

  it('surfaces an error when GET /api/settings fails', async () => {
    getSettingsMock.mockReset()
    getSettingsMock.mockRejectedValueOnce(new Error('boom'))
    const wrapper = mount(SettingsView)
    await flushPromises()

    expect(wrapper.find('[data-testid="load-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('加载失败')

    wrapper.unmount()
  })

  it('sends a PATCH /api/settings with the changed non-secret fields only', async () => {
    const wrapper = await mountView()
    await wrapper.find('#llm-base-url').setValue('https://api.example.com/v2')
    await wrapper.find('#llm-model').setValue('MiniMax-M2.5-custom')
    await flushPromises()

    await submitForm(wrapper)

    const payload = patchSettingsMock.mock.calls[0][0] as Record<string, unknown>
    expect(payload.llm_base_url).toBe('https://api.example.com/v2')
    expect(payload.llm_model).toBe('MiniMax-M2.5-custom')
    expect(payload).not.toHaveProperty('obsidian_vault_path') // unchanged

    wrapper.unmount()
  })

  it('renders the Wechat / Feishu panels with the same field names as the API response', async () => {
    const wrapper = await mountView()
    await wrapper.find('[data-testid="panel-feishu-header"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="panel-wechat-header"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('#feishu-webhook-url').exists()).toBe(true)
    expect(wrapper.find('#wechat-appid').exists()).toBe(true)
    expect(wrapper.find('#wechat-appsecret').exists()).toBe(true)

    wrapper.unmount()
  })
})