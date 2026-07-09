<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'

interface TaskProgress {
  task_id: string
  status: string
  progress_pct: number
  message: string
}

interface TaskCompletePayload {
  task_id: string
  status: string
  result?: { url?: string; title?: string }
  error_message?: string
}

interface TaskProgressPayload {
  task_id?: string
  status?: string
  url?: string
  title?: string | null
}

interface Task {
  id: string
  url: string
  status: string
  title: string | null
}

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

type ViewName = 'input' | 'tasks' | 'settings'

const currentView = ref<ViewName>('input')

const url = ref('')
const submitting = ref(false)
const inputMessage = ref('')
const progress = ref<TaskProgress>({
  task_id: '',
  status: '',
  progress_pct: 0,
  message: '',
})
const inputRef = ref<HTMLInputElement | null>(null)

const tasks = ref<Task[]>([])
const tasksMessage = ref('')

const settings = ref<Settings>({
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
const settingsMessage = ref('')

let isUnmounted = false
let unlistenProgress: UnlistenFn | null = null
let unlistenComplete: UnlistenFn | null = null
let unlistenTaskProgress: UnlistenFn | null = null

async function submit() {
  const target = url.value.trim()
  if (!target) return

  submitting.value = true
  inputMessage.value = ''
  progress.value = { task_id: '', status: 'running', progress_pct: 0, message: '提交中...' }

  try {
    await invoke('submit_url', { url: target, source: 'menubar' })
    inputMessage.value = '已加入处理队列'
    url.value = ''
  } catch (e) {
    inputMessage.value = `提交失败: ${e}`
    progress.value = { ...progress.value, status: '' }
  } finally {
    submitting.value = false
  }
}

async function loadTasks() {
  tasksMessage.value = ''
  try {
    const result = await invoke<{ tasks: Task[] }>('list_tasks', { limit: 50 })
    tasks.value = result.tasks || []
  } catch (e) {
    tasksMessage.value = `加载任务失败: ${e}`
  }
}

async function retryTask(taskId: string) {
  tasksMessage.value = ''
  try {
    await invoke('retry_task', { task_id: taskId })
  } catch (e) {
    tasksMessage.value = `重试失败: ${e}`
  }
}

async function loadSettings() {
  settingsMessage.value = ''
  try {
    const data = await invoke<Partial<Settings>>('get_settings')
    settings.value = { ...settings.value, ...data }
  } catch (e) {
    settingsMessage.value = `加载失败: ${e}`
  }
}

async function saveSettings() {
  saving.value = true
  settingsMessage.value = ''
  try {
    const payload: Partial<Settings> = {}
    for (const [key, value] of Object.entries(settings.value)) {
      if (typeof value === 'string' && value.includes('***')) {
        // Skip masked secrets so we don't overwrite the real value.
        continue
      }
      ;(payload as Record<string, unknown>)[key] = value
    }
    const updated = await invoke<Partial<Settings>>('update_settings', { settings: payload })
    if (updated && typeof updated === 'object') {
      settings.value = { ...settings.value, ...updated }
    }
    settingsMessage.value = '已保存'
  } catch (e) {
    settingsMessage.value = `保存失败: ${e}`
  } finally {
    saving.value = false
  }
}

async function openObsidian() {
  try {
    await invoke('open_obsidian')
  } catch (e) {
    inputMessage.value = `打开 Obsidian 失败: ${e}`
  }
}

async function switchView(view: ViewName) {
  currentView.value = view
  if (view === 'tasks') {
    await loadTasks()
  } else if (view === 'settings') {
    await loadSettings()
  }
}

async function hideOnEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    try {
      await invoke('hide_window', { label: 'input' })
    } catch (e) {
      inputMessage.value = `关闭窗口失败: ${e}`
    }
  }
}

onMounted(async () => {
  inputRef.value?.focus()
  window.addEventListener('keydown', hideOnEscape)

  const progressFn = await listen<TaskProgress>('task_progress', (event) => {
    progress.value = event.payload
  })
  const completeFn = await listen<TaskCompletePayload>('task_complete', (event) => {
    if (event.payload.status === 'success') {
      inputMessage.value = event.payload.result?.title
        ? `完成: ${event.payload.result.title}`
        : '处理完成'
    } else {
      inputMessage.value = `处理失败: ${event.payload.error_message || ''}`
    }
    progress.value = { task_id: '', status: '', progress_pct: 0, message: '' }
  })
  const taskProgressFn = await listen<TaskProgressPayload>('task_progress', (event) => {
    const payload = event.payload
    const taskId = payload.task_id
    const status = payload.status
    if (!taskId || !status) return

    const existingIndex = tasks.value.findIndex((t) => t.id === taskId)
    if (existingIndex >= 0) {
      tasks.value = tasks.value.map((task, index) =>
        index === existingIndex
          ? { ...task, status, title: payload.title ?? task.title }
          : task,
      )
    } else {
      tasks.value = [
        {
          id: taskId,
          url: payload.url || '',
          status,
          title: payload.title || null,
        },
        ...tasks.value,
      ]
    }
  })

  if (isUnmounted) {
    progressFn()
    completeFn()
    taskProgressFn()
  } else {
    unlistenProgress = progressFn
    unlistenComplete = completeFn
    unlistenTaskProgress = taskProgressFn
  }
})

onUnmounted(() => {
  isUnmounted = true
  window.removeEventListener('keydown', hideOnEscape)
  unlistenProgress?.()
  unlistenComplete?.()
  unlistenTaskProgress?.()
})
</script>

<template>
  <div class="app-container">
    <header class="app-header">
      <h1>{{ currentView === 'input' ? 'AIPulse' : currentView === 'tasks' ? '最近任务' : '设置' }}</h1>
    </header>

    <main class="app-content">
      <div v-if="currentView === 'input'" class="input-view">
        <input
          ref="inputRef"
          v-model="url"
          type="text"
          placeholder="粘贴 RSS / 视频 / 文章链接"
          @keydown.enter="submit"
        />
        <button :disabled="!url.trim() || submitting" @click="submit">
          {{ submitting ? '提交中...' : '开始处理' }}
        </button>
        <div v-if="progress.status" class="progress">
          <div class="progress-bar" :style="{ width: `${progress.progress_pct}%` }"></div>
          <span class="progress-text">{{ progress.message }}</span>
        </div>
        <p v-if="inputMessage" class="message">{{ inputMessage }}</p>
      </div>

      <div v-else-if="currentView === 'tasks'" class="tasks-view">
        <ul v-if="tasks.length">
          <li v-for="task in tasks" :key="task.id">
            <span class="status" :class="task.status">{{ task.status }}</span>
            <span class="title">{{ task.title || task.url }}</span>
            <button v-if="task.status === 'failed'" @click="retryTask(task.id)">重试</button>
          </li>
        </ul>
        <p v-else class="empty">暂无任务</p>
        <p v-if="tasksMessage" class="error">{{ tasksMessage }}</p>
      </div>

      <div v-else-if="currentView === 'settings'" class="settings-view">
        <div class="scrollable-content">
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
        </div>

        <div class="settings-actions">
          <button :disabled="saving" @click="saveSettings">{{ saving ? '保存中...' : '保存' }}</button>
          <p v-if="settingsMessage" class="message">{{ settingsMessage }}</p>
        </div>
      </div>
    </main>

    <nav class="app-tabs">
      <button :class="{ active: currentView === 'input' }" @click="switchView('input')">输入</button>
      <button :class="{ active: currentView === 'tasks' }" @click="switchView('tasks')">任务</button>
      <button :class="{ active: currentView === 'settings' }" @click="switchView('settings')">设置</button>
      <button @click="openObsidian">Obsidian</button>
    </nav>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: #fff;
}

.app-header {
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
  text-align: center;
}

.app-header h1 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.app-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.app-tabs {
  display: flex;
  border-top: 1px solid #eee;
  background: #fafafa;
}

.app-tabs button {
  flex: 1;
  padding: 12px 4px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: #666;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.app-tabs button.active {
  color: #0066ff;
  border-bottom-color: #0066ff;
  background: #fff;
}

.app-tabs button:hover {
  background: #f0f0f0;
}

/* Input view */
.input-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-view input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
}

.input-view button {
  padding: 10px 16px;
  background: #0066ff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}

.input-view button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.progress {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
}

.progress-bar {
  height: 4px;
  background: #0066ff;
  border-radius: 2px;
  transition: width 0.2s ease;
}

.progress-text {
  flex: 1;
}

.message {
  font-size: 13px;
  color: #666;
  margin: 0;
}

/* Tasks view */
.tasks-view ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tasks-view li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border: 1px solid #eee;
  border-radius: 6px;
}

.status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}

.status.pending { background: #f0f0f0; }
.status.running { background: #fff3cd; }
.status.completed { background: #d4edda; }
.status.failed { background: #f8d7da; }

.title {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tasks-view button {
  padding: 4px 8px;
  font-size: 12px;
  background: #0066ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.empty {
  color: #999;
  font-size: 13px;
}

.error {
  color: #d32f2f;
  font-size: 13px;
}

/* Settings view */
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.scrollable-content {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-right: 4px;
}

.settings-view section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.settings-view h3 {
  margin: 8px 0 0;
  font-size: 14px;
  color: #444;
}

.settings-view label {
  font-size: 13px;
  color: #666;
}

.settings-view input {
  padding: 8px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
}

.settings-actions {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eee;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.settings-actions button {
  padding: 10px 16px;
  background: #0066ff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.settings-actions button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
