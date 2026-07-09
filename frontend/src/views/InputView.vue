<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'

interface ProgressPayload {
  task_id: string
  status: string
  progress_pct: number
  message: string
}

interface TaskPayload {
  task_id: string
  status: string
  url?: string
  title?: string | null
}

interface TaskCompletePayload {
  task_id: string
  status: 'success' | 'failed'
  result?: { title?: string }
  error_message?: string
}

interface Task {
  id: string
  url: string
  status: string
  title: string | null
}

const PLACEHOLDER = '粘贴 RSS / 视频 / 文章链接'
const STATUS_HINT = '粘贴链接，开始处理'
const MAX_RECENT_TASKS = 3

const url = ref('')
const submitting = ref(false)
const statusMessage = ref('')
const progress = ref<ProgressPayload | null>(null)
const recentTasks = ref<Task[]>([])
const inputRef = ref<HTMLInputElement | null>(null)

let isActive = true
let unlistenProgress: UnlistenFn | null = null
let unlistenComplete: UnlistenFn | null = null

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return String(error)
}

async function handleSubmit() {
  const target = url.value.trim()
  if (!target || submitting.value) return

  submitting.value = true
  statusMessage.value = ''

  try {
    await invoke('submit_url', { url: target, source: 'menubar' })
    statusMessage.value = '已加入处理队列'
    url.value = ''
  } catch (error: unknown) {
    statusMessage.value = `提交失败: ${getErrorMessage(error)}`
  } finally {
    submitting.value = false
  }
}

async function handleEscape(event: KeyboardEvent) {
  if (event.key !== 'Escape') return
  try {
    await invoke('hide_window', { label: 'input' })
  } catch (error: unknown) {
    statusMessage.value = `关闭窗口失败: ${getErrorMessage(error)}`
  }
}

function isProgressPayload(payload: unknown): payload is ProgressPayload {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'progress_pct' in payload &&
    typeof (payload as Record<string, unknown>).progress_pct === 'number'
  )
}

function isTaskPayload(payload: unknown): payload is TaskPayload {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'task_id' in payload &&
    'status' in payload &&
    typeof (payload as Record<string, unknown>).task_id === 'string' &&
    typeof (payload as Record<string, unknown>).status === 'string'
  )
}

function updateProgress(payload: ProgressPayload) {
  progress.value = payload
}

function upsertRecentTask(payload: TaskPayload) {
  const { task_id: taskId, status, url: taskUrl, title } = payload
  const existingIndex = recentTasks.value.findIndex((task) => task.id === taskId)

  if (existingIndex >= 0) {
    recentTasks.value = recentTasks.value.map((task, index) =>
      index === existingIndex
        ? { ...task, status, title: title ?? task.title }
        : task,
    )
    return
  }

  const newTask: Task = {
    id: taskId,
    url: taskUrl || '',
    status,
    title: title ?? null,
  }

  recentTasks.value = [newTask, ...recentTasks.value].slice(0, MAX_RECENT_TASKS)
}

function handleTaskProgress(payload: ProgressPayload | TaskPayload) {
  if (isProgressPayload(payload)) {
    updateProgress(payload)
  }
  if (isTaskPayload(payload)) {
    upsertRecentTask(payload)
  }
}

function handleTaskComplete(payload: TaskCompletePayload) {
  progress.value = null

  if (payload.status === 'success') {
    statusMessage.value = payload.result?.title
      ? `完成: ${payload.result.title}`
      : '处理完成'
  } else {
    statusMessage.value = `处理失败: ${payload.error_message || ''}`
  }
}

onMounted(async () => {
  inputRef.value?.focus()
  window.addEventListener('keydown', handleEscape)

  unlistenProgress = await listen<ProgressPayload | TaskPayload>(
    'task_progress',
    (event) => handleTaskProgress(event.payload),
  )
  unlistenComplete = await listen<TaskCompletePayload>('task_complete', (event) =>
    handleTaskComplete(event.payload),
  )

  if (!isActive) {
    unlistenProgress?.()
    unlistenComplete?.()
    unlistenProgress = null
    unlistenComplete = null
  }
})

onUnmounted(() => {
  isActive = false
  window.removeEventListener('keydown', handleEscape)
  unlistenProgress?.()
  unlistenComplete?.()
})
</script>

<template>
  <div class="input-view">
    <div class="input-stage">
      <p class="status-hint">{{ STATUS_HINT }}</p>

      <input
        ref="inputRef"
        v-model="url"
        class="input-field"
        type="text"
        :placeholder="PLACEHOLDER"
        @keydown.enter="handleSubmit"
      />

      <button
        class="submit-button"
        :disabled="!url.trim() || submitting"
        @click="handleSubmit"
      >
        {{ submitting ? '提交中...' : '开始处理' }}
      </button>

      <div v-if="progress" class="progress">
        <div class="progress-track">
          <div
            class="progress-bar"
            :style="{ width: `${progress.progress_pct}%` }"
          ></div>
        </div>
        <span class="progress-text">{{ progress.message }}</span>
      </div>

      <p v-if="statusMessage" class="status-message">{{ statusMessage }}</p>
    </div>

    <div class="recent-tasks">
      <template v-if="recentTasks.length">
        <div
          v-for="task in recentTasks"
          :key="task.id"
          class="recent-task"
        >
          <span class="status-dot" :class="task.status"></span>
          <span class="task-title">{{ task.title || task.url }}</span>
        </div>
      </template>

      <div v-else class="empty-state">
        <svg
          class="empty-logo"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M12 2L2 7L12 12L22 7L12 2Z"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <path
            d="M2 17L12 22L22 17"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <path
            d="M2 12L12 17L22 12"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
        <span>还没有处理记录</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.input-view {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  padding: 32px;
  gap: 24px;
  overflow: auto;
}

.input-stage {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-hint {
  margin: 0;
  text-align: center;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.input-field {
  width: 100%;
  height: 64px;
  padding: 0 20px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  color: var(--text-primary);
  font-size: var(--text-lg);
  text-align: center;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.input-field::placeholder {
  color: var(--text-secondary);
}

.input-field:focus {
  border-color: var(--accent-coral);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent-coral) 20%, transparent);
}

.submit-button {
  width: 100%;
  height: 48px;
  background: var(--surface-elevated);
  border: 1px solid var(--accent-coral);
  border-radius: var(--radius-md);
  color: var(--accent-coral);
  font-size: var(--text-base);
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.submit-button:hover:not(:disabled) {
  background: var(--status-green);
  color: var(--surface-bg);
}

.submit-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.progress {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-track {
  width: 100%;
  height: 2px;
  background: var(--border-subtle);
  border-radius: 1px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--status-green);
  transition: width 0.2s ease;
}

.progress-text {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.status-message {
  margin: 0;
  text-align: center;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.recent-tasks {
  width: 100%;
  max-width: 640px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.recent-task {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}

.status-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-secondary);
}

.status-dot.running {
  background: var(--status-amber);
}

.status-dot.completed {
  background: var(--status-green);
}

.status-dot.failed {
  background: var(--status-red);
}

.task-title {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.empty-logo {
  width: 40px;
  height: 40px;
  opacity: 0.15;
}
</style>
