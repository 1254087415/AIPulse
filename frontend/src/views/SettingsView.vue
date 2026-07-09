<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'

interface Settings {
  obsidian_vault_path: string
  obsidian_archive_folder: string
  llm_api_key: string
  llm_base_url: string
  llm_model: string
  feishu_webhook_url: string
  feishu_secret: string
  wechat_appid: string
  wechat_appsecret: string
  wechat_template_id: string
  wechat_openid: string
}

interface PanelState {
  llm: boolean
  obsidian: boolean
  feishu: boolean
  wechat: boolean
}

const PASSWORD_FIELDS = new Set([
  'llm_api_key',
  'feishu_secret',
  'wechat_appsecret',
])

const settings = reactive<Settings>({
  obsidian_vault_path: '',
  obsidian_archive_folder: 'AIPulse',
  llm_api_key: '',
  llm_base_url: 'https://api.kimi.com/coding/v1',
  llm_model: 'kimi-for-coding',
  feishu_webhook_url: '',
  feishu_secret: '',
  wechat_appid: '',
  wechat_appsecret: '',
  wechat_template_id: '',
  wechat_openid: '',
})

const expanded = ref<PanelState>({
  llm: true,
  obsidian: false,
  feishu: false,
  wechat: false,
})

const passwordVisible = ref<Record<string, boolean>>({
  llm_api_key: false,
  feishu_secret: false,
  wechat_appsecret: false,
})

const saving = ref(false)
const saved = ref(false)
const errorMessage = ref('')

let savedTimer: ReturnType<typeof setTimeout> | null = null

function togglePanel(key: keyof PanelState) {
  expanded.value = { ...expanded.value, [key]: !expanded.value[key] }
}

function togglePassword(field: string) {
  passwordVisible.value = { ...passwordVisible.value, [field]: !passwordVisible.value[field] }
}

function getInputType(field: keyof Settings) {
  if (!PASSWORD_FIELDS.has(field)) {
    return 'text'
  }
  return passwordVisible.value[field] ? 'text' : 'password'
}

function buildPayload(): Partial<Settings> {
  const payload: Partial<Settings> = {}
  for (const [key, value] of Object.entries(settings)) {
    if (typeof value === 'string' && value.includes('***')) {
      continue
    }
    ;(payload as Record<string, unknown>)[key] = value
  }
  return payload
}

async function save() {
  saving.value = true
  saved.value = false
  errorMessage.value = ''
  if (savedTimer) {
    clearTimeout(savedTimer)
    savedTimer = null
  }

  try {
    const payload = buildPayload()
    const updated = await invoke<Partial<Settings>>('update_settings', { settings: payload })
    if (updated && typeof updated === 'object') {
      Object.assign(settings, updated)
    }
    saved.value = true
    savedTimer = setTimeout(() => {
      saved.value = false
    }, 1500)
  } catch {
    errorMessage.value = '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const data = await invoke<Partial<Settings>>('get_settings')
    Object.assign(settings, data)
  } catch {
    errorMessage.value = '加载失败，请重试'
  }
})

onUnmounted(() => {
  if (savedTimer) {
    clearTimeout(savedTimer)
  }
})
</script>

<template>
  <div class="settings-container">
    <h2 class="settings-title">设置</h2>

    <div class="scrollable-content">
      <div
        class="panel"
        :class="{ 'is-expanded': expanded.llm }"
        data-testid="panel-llm"
      >
        <button
          class="panel-header"
          data-testid="panel-llm-header"
          @click="togglePanel('llm')"
        >
          <span class="panel-icon" aria-hidden="true">{{ expanded.llm ? '▼' : '▶' }}</span>
          <span class="panel-title">Kimi Code LLM</span>
        </button>
        <div class="panel-body">
          <label for="llm-api-key">API Key</label>
          <div class="password-field">
            <input
              id="llm-api-key"
              v-model="settings.llm_api_key"
              :type="getInputType('llm_api_key')"
            />
            <button
              type="button"
              class="toggle-password"
              data-testid="toggle-llm-api-key"
              @click="togglePassword('llm_api_key')"
            >
              {{ passwordVisible.llm_api_key ? '隐藏' : '显示' }}
            </button>
          </div>

          <label for="llm-base-url">Base URL</label>
          <input id="llm-base-url" v-model="settings.llm_base_url" type="text" />

          <label for="llm-model">Model</label>
          <input id="llm-model" v-model="settings.llm_model" type="text" />
        </div>
      </div>

      <div
        class="panel"
        :class="{ 'is-expanded': expanded.obsidian }"
        data-testid="panel-obsidian"
      >
        <button
          class="panel-header"
          data-testid="panel-obsidian-header"
          @click="togglePanel('obsidian')"
        >
          <span class="panel-icon" aria-hidden="true">{{ expanded.obsidian ? '▼' : '▶' }}</span>
          <span class="panel-title">Obsidian</span>
        </button>
        <div class="panel-body">
          <label for="obsidian-vault-path">Vault 路径</label>
          <input id="obsidian-vault-path" v-model="settings.obsidian_vault_path" type="text" />

          <label for="obsidian-archive-folder">归档文件夹</label>
          <input
            id="obsidian-archive-folder"
            v-model="settings.obsidian_archive_folder"
            type="text"
          />
        </div>
      </div>

      <div
        class="panel"
        :class="{ 'is-expanded': expanded.feishu }"
        data-testid="panel-feishu"
      >
        <button
          class="panel-header"
          data-testid="panel-feishu-header"
          @click="togglePanel('feishu')"
        >
          <span class="panel-icon" aria-hidden="true">{{ expanded.feishu ? '▼' : '▶' }}</span>
          <span class="panel-title">飞书推送</span>
        </button>
        <div class="panel-body">
          <label for="feishu-webhook-url">Webhook URL</label>
          <input id="feishu-webhook-url" v-model="settings.feishu_webhook_url" type="text" />

          <label for="feishu-secret">Secret</label>
          <div class="password-field">
            <input
              id="feishu-secret"
              v-model="settings.feishu_secret"
              :type="getInputType('feishu_secret')"
            />
            <button
              type="button"
              class="toggle-password"
              data-testid="toggle-feishu-secret"
              @click="togglePassword('feishu_secret')"
            >
              {{ passwordVisible.feishu_secret ? '隐藏' : '显示' }}
            </button>
          </div>
        </div>
      </div>

      <div
        class="panel"
        :class="{ 'is-expanded': expanded.wechat }"
        data-testid="panel-wechat"
      >
        <button
          class="panel-header"
          data-testid="panel-wechat-header"
          @click="togglePanel('wechat')"
        >
          <span class="panel-icon" aria-hidden="true">{{ expanded.wechat ? '▼' : '▶' }}</span>
          <span class="panel-title">微信推送</span>
        </button>
        <div class="panel-body">
          <label for="wechat-appid">AppID</label>
          <input id="wechat-appid" v-model="settings.wechat_appid" type="text" />

          <label for="wechat-appsecret">AppSecret</label>
          <div class="password-field">
            <input
              id="wechat-appsecret"
              v-model="settings.wechat_appsecret"
              :type="getInputType('wechat_appsecret')"
            />
            <button
              type="button"
              class="toggle-password"
              data-testid="toggle-wechat-appsecret"
              @click="togglePassword('wechat_appsecret')"
            >
              {{ passwordVisible.wechat_appsecret ? '隐藏' : '显示' }}
            </button>
          </div>

          <label for="wechat-template-id">Template ID</label>
          <input id="wechat-template-id" v-model="settings.wechat_template_id" type="text" />

          <label for="wechat-openid">OpenID</label>
          <input id="wechat-openid" v-model="settings.wechat_openid" type="text" />
        </div>
      </div>
    </div>

    <div class="actions">
      <button
        class="save-button"
        data-testid="save-button"
        :disabled="saving"
        @click="save"
      >
        {{ saving ? '保存中...' : saved ? '已保存' : '保存' }}
      </button>
      <p v-if="errorMessage" class="error-message" data-testid="save-error">
        {{ errorMessage }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.settings-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.settings-title {
  margin: 0;
  padding: 20px 20px 12px;
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
}

.scrollable-content {
  flex: 1;
  overflow-y: auto;
  padding: 0 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel {
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.panel-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
}

.panel-header:hover {
  background: var(--surface-elevated-hover);
}

.panel-icon {
  font-size: 12px;
  color: var(--text-secondary);
  transition: transform 0.2s ease;
}

.panel.is-expanded .panel-icon {
  transform: rotate(0deg);
}

.panel-body {
  max-height: 0;
  overflow: hidden;
  padding: 0 16px;
  transition: max-height 0.2s ease, padding 0.2s ease;
}

.panel.is-expanded .panel-body {
  max-height: 600px;
  padding: 0 16px 16px;
}

label {
  display: block;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin: 12px 0 6px;
}

input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: var(--text-sm);
  box-sizing: border-box;
}

input:focus {
  outline: none;
  border-color: var(--accent-coral);
}

.password-field {
  position: relative;
}

.password-field input {
  padding-right: 44px;
}

.toggle-password {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  padding: 4px 6px;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  cursor: pointer;
}

.toggle-password:hover {
  color: var(--text-primary);
}

.actions {
  padding: 12px 20px 20px;
  border-top: 1px solid var(--border-subtle);
  background: var(--surface-bg);
}

.save-button {
  width: 100%;
  height: 40px;
  background: var(--surface-elevated);
  border: 1px solid var(--accent-coral);
  border-radius: var(--radius-sm);
  color: var(--accent-coral);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.1s ease, color 0.1s ease, transform 0.1s ease;
}

.save-button:hover:not(:disabled) {
  background: var(--accent-coral);
  color: var(--surface-bg);
}

.save-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.save-button:active:not(:disabled) {
  transform: scale(0.98);
}

.error-message {
  margin: 8px 0 0;
  font-size: var(--text-xs);
  color: var(--status-red);
  text-align: center;
}

@media (prefers-reduced-motion: reduce) {
  .panel-icon,
  .panel-body,
  .save-button,
  input {
    transition: none;
  }

  .save-button:active:not(:disabled) {
    transform: none;
  }
}
</style>
