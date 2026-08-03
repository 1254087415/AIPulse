<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted } from 'vue'
import AppButton from '../components/ui/AppButton.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import { getSettings, patchSettings, type SettingsResponse } from '../api/settings'
import { setApiToken } from '../lib/settings-store'

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
  aipulse_api_token: string
}

interface PanelState {
  llm: boolean
  obsidian: boolean
  feishu: boolean
  wechat: boolean
  api_auth: boolean
}

const PASSWORD_FIELDS = new Set([
  'llm_api_key',
  'feishu_secret',
  'wechat_appsecret',
  'aipulse_api_token',
])

const settings = reactive<Settings>({
  obsidian_vault_path: '',
  obsidian_archive_folder: 'AIPulse',
  llm_api_key: '',
  llm_base_url: 'https://api.minimaxi.com/v1',
  llm_model: 'MiniMax-M2.5',
  feishu_webhook_url: '',
  feishu_secret: '',
  wechat_appid: '',
  wechat_appsecret: '',
  wechat_template_id: '',
  wechat_openid: '',
  aipulse_api_token: '',
})

const expanded = ref<PanelState>({
  llm: true,
  obsidian: false,
  feishu: false,
  wechat: false,
  api_auth: false,
})

const passwordVisible = ref<Record<string, boolean>>({
  llm_api_key: false,
  feishu_secret: false,
  wechat_appsecret: false,
  aipulse_api_token: false,
})

const saving = ref(false)
const saved = ref(false)
const errorMessage = ref('')
const loadError = ref('')
const vaultPickerMessage = ref('')

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

function isMaskedSecret(value: string): boolean {
  // The backend masks secrets as either `***` (short values) or
  // `first4***last4` (>= 8 chars). Either form must NOT be sent back —
  // doing so would overwrite the real secret with the placeholder.
  return value.includes('***')
}

let initialSnapshot: Record<string, string> = {}

function applySettings(data: SettingsResponse): void {
  settings.llm_api_key = data.llm?.llm_api_key ?? ''
  settings.llm_base_url = data.llm?.llm_base_url ?? settings.llm_base_url
  settings.llm_model = data.llm?.llm_model ?? settings.llm_model
  settings.obsidian_vault_path = data.obsidian?.obsidian_vault_path ?? ''
  settings.obsidian_archive_folder =
    data.obsidian?.obsidian_archive_folder ?? settings.obsidian_archive_folder
  settings.feishu_webhook_url = data.feishu?.feishu_webhook_url ?? ''
  settings.feishu_secret = data.feishu?.feishu_secret ?? ''
  settings.wechat_appid = data.wechat?.wechat_appid ?? ''
  settings.wechat_appsecret = data.wechat?.wechat_appsecret ?? ''
  settings.wechat_template_id = data.wechat?.wechat_template_id ?? ''
  settings.wechat_openid = data.wechat?.wechat_openid ?? ''
  settings.aipulse_api_token = data.api_auth?.aipulse_api_token ?? ''
  initialSnapshot = { ...settings }
}

function buildPayload(): Partial<Settings> {
  // Only include fields the user has actually touched since the last load.
  // Masked secrets and empty values are skipped so the backend preserves
  // the existing secret (CLAUDE.md §4 + spec §10.1).
  const payload: Partial<Settings> = {}
  for (const [key, value] of Object.entries(settings)) {
    if (PASSWORD_FIELDS.has(key)) {
      if (!value || isMaskedSecret(value)) continue
    }
    if (value === initialSnapshot[key]) continue
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
    const updated = await patchSettings(payload)
    if (payload.aipulse_api_token) {
      setApiToken(payload.aipulse_api_token)
    }
    applySettings(updated)
    saved.value = true
    savedTimer = setTimeout(() => {
      saved.value = false
    }, 1500)
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? `保存失败：${error.message}` : '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

function handleSubmit(): void {
  void save()
}

interface PickedDirectory {
  name: string
  path: string
}

async function pickObsidianVault(): Promise<void> {
  vaultPickerMessage.value = ''
  try {
    const dir = await pickDirectory()
    if (!dir) return
    settings.obsidian_vault_path = dir.path
    vaultPickerMessage.value = `已选择：${dir.name}`
  } catch (error: unknown) {
    vaultPickerMessage.value =
      error instanceof Error ? `选择失败：${error.message}` : '选择失败，请重试'
  }
}

async function pickDirectory(): Promise<PickedDirectory | null> {
  const picker = (window as unknown as {
    showDirectoryPicker?: () => Promise<{ kind: string; name: string }>
  }).showDirectoryPicker
  if (typeof picker === 'function') {
    const handle = await picker()
    return { name: handle.name, path: handle.name }
  }
  return pickDirectoryViaInput()
}

function pickDirectoryViaInput(): Promise<PickedDirectory | null> {
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.webkitdirectory = true
    input.style.display = 'none'
    input.addEventListener(
      'change',
      () => {
        const files = input.files
        const first = files && files[0]
        const dirName = first ? first.webkitRelativePath.split('/')[0] : ''
        document.body.removeChild(input)
        if (!dirName) {
          resolve(null)
          return
        }
        resolve({ name: dirName, path: dirName })
      },
      { once: true },
    )
    document.body.appendChild(input)
    input.click()
  })
}

onMounted(async () => {
  try {
    const data = await getSettings()
    applySettings(data)
  } catch {
    loadError.value = '加载失败，请重试'
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
    <PageHeader title="设置" subtitle="LLM / Obsidian / 推送 / API 鉴权" />

    <p v-if="loadError" class="load-error" data-testid="load-error" role="alert">
      {{ loadError }}
    </p>

    <form class="settings-form" @submit.prevent="handleSubmit">
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
          <span class="panel-title">LLM</span>
        </button>
        <div class="panel-body">
          <label for="llm-api-key">API Key</label>
          <div class="password-field">
            <input
              id="llm-api-key"
              v-model="settings.llm_api_key"
              :type="getInputType('llm_api_key')"
            />
            <AppButton
              size="sm"
              variant="ghost"
              class="toggle-password"
              data-testid="toggle-llm-api-key"
              @click="togglePassword('llm_api_key')"
            >
              {{ passwordVisible.llm_api_key ? '隐藏' : '显示' }}
            </AppButton>
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
          <div class="vault-path-row">
            <input id="obsidian-vault-path" v-model="settings.obsidian_vault_path" type="text" />
            <AppButton
              variant="secondary"
              size="sm"
              data-testid="pick-obsidian-vault"
              @click="pickObsidianVault"
            >
              选择目录
            </AppButton>
          </div>
          <p
            v-if="vaultPickerMessage"
            class="vault-picker-status"
            data-testid="vault-picker-status"
            role="status"
          >
            {{ vaultPickerMessage }}
          </p>

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
            <AppButton
              size="sm"
              variant="ghost"
              class="toggle-password"
              data-testid="toggle-feishu-secret"
              @click="togglePassword('feishu_secret')"
            >
              {{ passwordVisible.feishu_secret ? '隐藏' : '显示' }}
            </AppButton>
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
            <AppButton
              size="sm"
              variant="ghost"
              class="toggle-password"
              data-testid="toggle-wechat-appsecret"
              @click="togglePassword('wechat_appsecret')"
            >
              {{ passwordVisible.wechat_appsecret ? '隐藏' : '显示' }}
            </AppButton>
          </div>

          <label for="wechat-template-id">Template ID</label>
          <input id="wechat-template-id" v-model="settings.wechat_template_id" type="text" />

          <label for="wechat-openid">OpenID</label>
          <input id="wechat-openid" v-model="settings.wechat_openid" type="text" />
        </div>
      </div>

      <div
        class="panel"
        :class="{ 'is-expanded': expanded.api_auth }"
        data-testid="panel-api-auth"
      >
        <button
          class="panel-header"
          data-testid="panel-api-auth-header"
          @click="togglePanel('api_auth')"
        >
          <span class="panel-icon" aria-hidden="true">{{ expanded.api_auth ? '▼' : '▶' }}</span>
          <span class="panel-title">API 鉴权</span>
        </button>
        <div class="panel-body">
          <label for="aipulse-api-token">AIPulse API Token</label>
          <div class="password-field">
            <input
              id="aipulse-api-token"
              v-model="settings.aipulse_api_token"
              :type="getInputType('aipulse_api_token')"
              placeholder="留空表示不启用 Bearer 鉴权"
            />
            <AppButton
              size="sm"
              variant="ghost"
              class="toggle-password"
              data-testid="toggle-aipulse-api-token"
              @click="togglePassword('aipulse_api_token')"
            >
              {{ passwordVisible.aipulse_api_token ? '隐藏' : '显示' }}
            </AppButton>
          </div>
          <p class="panel-hint" data-testid="aipulse-token-hint">
            配置后所有 <code>/api/*</code> 请求必须携带 <code>Authorization: Bearer &lt;token&gt;</code>。
            留空则不鉴权（开发模式）。
          </p>
        </div>
      </div>
    </div>

      <div class="actions">
        <AppButton
          type="submit"
          variant="primary"
          block
          :loading="saving"
          data-testid="save-button"
        >
          {{ saving ? '保存中...' : saved ? '已保存' : '保存' }}
        </AppButton>
        <p v-if="errorMessage" class="error-message" data-testid="save-error">
          {{ errorMessage }}
        </p>
      </div>
    </form>
  </div>
</template>

<style scoped>
.settings-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  padding: 20px 20px 0;
}

.settings-form {
  display: contents;
}

.load-error {
  margin: 0 0 12px;
  padding: 10px 12px;
  background: color-mix(in srgb, var(--status-red) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--status-red) 30%, transparent);
  border-radius: var(--radius-md);
  color: var(--status-red);
  font-size: 13px;
}

.scrollable-content {
  flex: 1;
  overflow-y: auto;
  padding: 0;
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
  padding-right: 80px;
}

.toggle-password {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
}

.vault-path-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.vault-path-row input {
  flex: 1;
}

.actions {
  padding: 12px 0 20px;
}

.error-message {
  margin: 8px 0 0;
  font-size: var(--text-xs);
  color: var(--status-red);
  text-align: center;
}

.panel-hint {
  margin: 8px 0 0;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.panel-hint code {
  background: var(--surface-bg);
  padding: 1px 4px;
  border-radius: 4px;
  font-family: var(--font-mono, monospace);
  font-size: 11px;
}

@media (prefers-reduced-motion: reduce) {
  .panel-icon,
  .panel-body,
  input {
    transition: none;
  }
}
</style>