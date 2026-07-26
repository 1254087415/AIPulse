/**
 * Settings API client — typed wrapper around `/api/settings`.
 *
 * GET returns the grouped form (`{kimi, obsidian, wechat, feishu}`).
 * PATCH accepts the flat form and updates any subset of fields.
 */

import { apiFetch } from '../lib/apiFetch'

export interface KimiGroup {
  kimi_api_key: string
  kimi_base_url: string
  kimi_model: string
  learning_notification_enabled: boolean
}

export interface ObsidianGroup {
  obsidian_vault_path: string
  obsidian_archive_folder: string
}

export interface WechatGroup {
  wechat_appid: string
  wechat_appsecret: string
  wechat_template_id: string
  wechat_openid: string
  wechat_to_user?: string
  wechat_account_id?: string
  wechat_bot_token?: string
  wechat_context_token_file?: string
  wechat_send_script?: string
}

export interface FeishuGroup {
  feishu_webhook_url: string
  feishu_secret: string
}

export interface SettingsResponse {
  kimi: KimiGroup
  obsidian: ObsidianGroup
  wechat: WechatGroup
  feishu: FeishuGroup
}

export type SettingsPatch = Partial<{
  kimi_api_key: string
  kimi_base_url: string
  kimi_model: string
  learning_notification_enabled: boolean
  obsidian_vault_path: string
  obsidian_archive_folder: string
  wechat_appid: string
  wechat_appsecret: string
  wechat_template_id: string
  wechat_openid: string
  wechat_to_user: string
  wechat_account_id: string
  wechat_bot_token: string
  wechat_context_token_file: string
  wechat_send_script: string
  feishu_webhook_url: string
  feishu_secret: string
}>

export async function getSettings(): Promise<SettingsResponse> {
  const response = await apiFetch<{ success: boolean; data: SettingsResponse }>('/api/settings')
  return response.data
}

export async function patchSettings(changes: SettingsPatch): Promise<SettingsResponse> {
  const response = await apiFetch<{ success: boolean; data: SettingsResponse }>(
    '/api/settings',
    { method: 'PATCH', body: JSON.stringify(changes) },
  )
  return response.data
}