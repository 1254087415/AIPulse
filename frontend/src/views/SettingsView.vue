<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
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

const saving = ref(false)
const message = ref('')

async function save() {
  saving.value = true
  message.value = ''
  try {
    const updated = await invoke<Partial<Settings>>('update_settings', { settings })
    if (updated && typeof updated === 'object') {
      Object.assign(settings, updated)
    }
    message.value = '已保存'
  } catch (e) {
    message.value = `保存失败: ${e}`
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const data = await invoke<Partial<Settings>>('get_settings')
    Object.assign(settings, data)
  } catch (e) {
    message.value = `加载失败: ${e}`
  }
})
</script>

<template>
  <div class="settings-container">
    <h2>设置</h2>

    <section>
      <h3>Kimi Code LLM</h3>
      <label for="llm-api-key">API Key</label>
      <input id="llm-api-key" v-model="settings.llm_api_key" type="password" />
      <label for="llm-base-url">Base URL</label>
      <input id="llm-base-url" v-model="settings.llm_base_url" type="text" />
      <label for="llm-model">Model</label>
      <input id="llm-model" v-model="settings.llm_model" type="text" />
    </section>

    <section>
      <h3>Obsidian</h3>
      <label for="obsidian-vault-path">Vault 路径</label>
      <input id="obsidian-vault-path" v-model="settings.obsidian_vault_path" type="text" />
      <label for="obsidian-archive-folder">归档文件夹</label>
      <input id="obsidian-archive-folder" v-model="settings.obsidian_archive_folder" type="text" />
    </section>

    <section>
      <h3>飞书推送</h3>
      <label for="feishu-webhook-url">Webhook URL</label>
      <input id="feishu-webhook-url" v-model="settings.feishu_webhook_url" type="text" />
      <label for="feishu-secret">Secret</label>
      <input id="feishu-secret" v-model="settings.feishu_secret" type="password" />
    </section>

    <section>
      <h3>微信推送</h3>
      <label for="wechat-appid">AppID</label>
      <input id="wechat-appid" v-model="settings.wechat_appid" type="text" />
      <label for="wechat-appsecret">AppSecret</label>
      <input id="wechat-appsecret" v-model="settings.wechat_appsecret" type="password" />
      <label for="wechat-template-id">Template ID</label>
      <input id="wechat-template-id" v-model="settings.wechat_template_id" type="text" />
      <label for="wechat-openid">OpenID</label>
      <input id="wechat-openid" v-model="settings.wechat_openid" type="text" />
    </section>

    <button :disabled="saving" @click="save">{{ saving ? '保存中...' : '保存' }}</button>
    <p v-if="message" class="message">{{ message }}</p>
  </div>
</template>

<style scoped>
.settings-container {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 100vh;
  overflow-y: auto;
}

section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

h2 {
  margin: 0;
  font-size: 18px;
}

h3 {
  margin: 8px 0 0;
  font-size: 14px;
  color: #444;
}

label {
  font-size: 13px;
  color: #666;
}

input {
  padding: 8px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
}

button {
  padding: 10px 16px;
  background: #0066ff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.message {
  font-size: 13px;
  color: #666;
}
</style>
