import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import SettingsView from '../SettingsView.vue'
import type { SettingsResponse } from '../../types'

const mockSettings: SettingsResponse = {
  kimi: {
    kimi_api_key: 'sk-***masked***',
    kimi_base_url: 'https://api.kimi.com/coding/v1',
    kimi_model: 'kimi-for-coding',
    learning_notification_enabled: true,
  },
  obsidian: {
    obsidian_vault_path: '/Users/me/Obsidian',
    obsidian_archive_folder: 'AIPulse',
  },
  wechat: {
    wechat_appid: 'wx-test',
    wechat_appsecret: '***',
    wechat_template_id: 'tpl-1',
    wechat_openid: 'oid-1',
    wechat_to_user: 'all',
    wechat_account_id: 'acct-1',
    wechat_bot_token: '***',
    wechat_context_token_file: '/tmp/wx.json',
    wechat_send_script: '',
  },
  feishu: {
    feishu_webhook_url: 'https://open.feishu.cn/hook',
    feishu_secret: '***',
  },
}

function jsonResponse(data: unknown) {
  return new Response(JSON.stringify({ success: true, data }), { status: 200 })
}

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return mount(SettingsView, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
    },
  })
}

describe('SettingsView — 微信分组字段（[L1] 返工守护）', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('渲染 wechat_bot_token / wechat_context_token_file / wechat_send_script', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(mockSettings)))

    const wrapper = makeWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('机器人 Token')
    // `wechat_bot_token` 是 masked 字段，不回填真实值（保持 UI 一致）
    expect(wrapper.text()).not.toContain('***masked***')
    expect(wrapper.text()).toContain('上下文 Token 文件路径')
    expect(wrapper.text()).toContain('发送脚本路径')
  })

  it('渲染 wechat_to_user 默认字符串不被 mask 字段影响', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(mockSettings)))

    const wrapper = makeWrapper()
    await flushPromises()

    // 微信分组下既有 mask 字段（AppSecret、bot_token）也有普通字段（OpenID、To User）
    // 共同渲染 → 防止后续重构里 if 分支错误导致整组消失
    expect(wrapper.text()).toContain('To User')
    expect(wrapper.text()).toContain('OpenID')
  })
})
