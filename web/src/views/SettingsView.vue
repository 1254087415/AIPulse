<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { fetchSettings, updateSettings } from '../api/settings'
import type { SettingsResponse, SettingsUpdate } from '../types'

const queryClient = useQueryClient()
const { data, isLoading, error } = useQuery({
  queryKey: ['settings'],
  queryFn: fetchSettings,
})

const draft = reactive<SettingsUpdate>({})
const feedback = ref<string | null>(null)

watch(
  () => data.value,
  (next) => {
    if (!next) return
    Object.keys(draft).forEach((k) => delete draft[k])
  },
)

const sections = computed(() => {
  if (!data.value) return []
  return [
    { key: 'kimi' as const, title: 'Kimi', fields: kimiFields(data.value) },
    { key: 'obsidian' as const, title: 'Obsidian', fields: obsidianFields(data.value) },
    { key: 'wechat' as const, title: '微信', fields: wechatFields(data.value) },
    { key: 'feishu' as const, title: '飞书', fields: feishuFields(data.value) },
  ]
})

interface SettingsField {
  key: string
  label: string
  masked?: boolean
  type?: 'boolean'
  value?: string | number | boolean
}

function kimiFields(s: SettingsResponse): SettingsField[] {
  return [
    { key: 'kimi_api_key', label: 'API Key', masked: true },
    { key: 'kimi_base_url', label: 'Base URL', value: s.kimi.kimi_base_url ?? '' },
    { key: 'kimi_model', label: 'Model', value: s.kimi.kimi_model ?? '' },
    {
      key: 'learning_notification_enabled',
      label: '启用学习通知',
      value: s.kimi.learning_notification_enabled ?? true,
      type: 'boolean',
    },
  ]
}

function obsidianFields(s: SettingsResponse): SettingsField[] {
  return [
    { key: 'obsidian_vault_path', label: 'Vault 路径', value: s.obsidian.obsidian_vault_path ?? '' },
    { key: 'obsidian_archive_folder', label: '归档子目录', value: s.obsidian.obsidian_archive_folder ?? '' },
  ]
}

function wechatFields(s: SettingsResponse): SettingsField[] {
  return [
    { key: 'wechat_appid', label: 'AppID', value: s.wechat.wechat_appid ?? '' },
    { key: 'wechat_appsecret', label: 'AppSecret', masked: true },
    { key: 'wechat_template_id', label: 'Template ID', value: s.wechat.wechat_template_id ?? '' },
    { key: 'wechat_openid', label: 'OpenID', value: s.wechat.wechat_openid ?? '' },
    { key: 'wechat_to_user', label: 'To User', value: s.wechat.wechat_to_user ?? '' },
    { key: 'wechat_account_id', label: 'Account ID', value: s.wechat.wechat_account_id ?? '' },
    {
      key: 'wechat_bot_token',
      label: '机器人 Token (企业微信)',
      masked: true,
      // 不强制 value: 后端 settings_map 已包含此字段，缺省空串代表未设置
    },
    {
      key: 'wechat_context_token_file',
      label: '上下文 Token 文件路径',
      value: s.wechat.wechat_context_token_file ?? '',
    },
    {
      key: 'wechat_send_script',
      label: '发送脚本路径',
      value: s.wechat.wechat_send_script ?? '',
    },
  ]
}

function feishuFields(s: SettingsResponse): SettingsField[] {
  return [
    { key: 'feishu_webhook_url', label: 'Webhook URL', value: s.feishu.feishu_webhook_url ?? '' },
    { key: 'feishu_secret', label: '签名密钥', masked: true },
  ]
}

const save = useMutation({
  mutationFn: (payload: SettingsUpdate) => updateSettings(payload),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['settings'] })
    Object.keys(draft).forEach((k) => delete draft[k])
    feedback.value = '保存成功'
    setTimeout(() => (feedback.value = null), 2000)
  },
  onError: (err) => {
    feedback.value = `保存失败：${err instanceof Error ? err.message : '未知错误'}`
  },
})

function saveSection(sectionKey: string, fields: Array<{ key: string }>) {
  const payload: SettingsUpdate = {}
  for (const field of fields) {
    if (field.key in draft) {
      payload[field.key] = draft[field.key]
    }
  }
  if (Object.keys(payload).length === 0) {
    feedback.value = `${sectionKey} 没有改动`
    setTimeout(() => (feedback.value = null), 2000)
    return
  }
  save.mutate(payload)
}

function saveAll() {
  save.mutate({ ...draft })
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div class="page-title">
        <h1>设置</h1>
        <p class="subtitle">Kimi / Obsidian / 微信 / 飞书 的运行时配置</p>
      </div>
      <button
        type="button"
        class="btn primary"
        :disabled="Object.keys(draft).length === 0 || save.isPending.value"
        @click="saveAll"
      >
        {{ save.isPending.value ? '保存中…' : '全部保存' }}
      </button>
    </header>

    <p v-if="feedback" class="feedback" role="status" aria-live="polite">{{ feedback }}</p>

    <div v-if="isLoading" class="state state-loading">正在加载…</div>
    <div v-else-if="error" class="state state-error">加载失败：{{ error?.message }}</div>

    <section
      v-for="section in sections"
      v-else
      :key="section.key"
      class="panel"
      :aria-label="`${section.title} 设置`"
    >
      <header class="panel-header">
        <h2>{{ section.title }}</h2>
        <button
          type="button"
          class="btn"
          :disabled="save.isPending.value"
          @click="saveSection(section.title, section.fields)"
        >
          保存 {{ section.title }}
        </button>
      </header>

      <div class="fields">
        <div v-for="field in section.fields" :key="field.key" class="field">
          <label :for="field.key">{{ field.label }}</label>
          <input
            v-if="field.type !== 'boolean'"
            :id="field.key"
            v-model="draft[field.key]"
            :type="field.masked ? 'password' : 'text'"
            :placeholder="field.masked ? '留空保持原值' : (field.value != null ? String(field.value) : '')"
            autocomplete="off"
          />
          <select v-else :id="field.key" v-model="draft[field.key]">
            <option :value="true">启用</option>
            <option :value="false">关闭</option>
          </select>
          <p v-if="field.masked" class="hint">当前已保存密钥为 <code>***</code>，留空保持不变。</p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}

.subtitle {
  font-size: 13px;
  color: var(--slate);
  margin: 4px 0 0;
}

.feedback {
  background: rgba(58, 175, 169, 0.12);
  border: 1px solid var(--signal);
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--ink);
}

.panel {
  background: var(--color-surface, #fff);
  border: 1px solid var(--mist);
  border-radius: 10px;
  padding: 18px;
  margin-bottom: 18px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-header h2 {
  font-size: 16px;
}

.fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.field label {
  display: block;
  font-size: 12px;
  color: var(--slate);
  margin-bottom: 4px;
  font-weight: 600;
}

.field input,
.field select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--mist);
  border-radius: 6px;
  font-size: 14px;
  background: var(--color-surface, #fff);
}

.hint {
  font-size: 11px;
  color: var(--slate);
  margin: 4px 0 0;
}

.hint code {
  background: rgba(0, 0, 0, 0.04);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
}

.btn {
  padding: 8px 14px;
  border: 1px solid var(--mist);
  border-radius: 6px;
  background: var(--color-surface, #fff);
  font-size: 14px;
  cursor: pointer;
  color: var(--ink);
}

.btn.primary {
  background: var(--signal);
  border-color: var(--signal);
  color: #fff;
}

.btn[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>