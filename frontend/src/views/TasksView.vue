<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'

interface Task {
  id: string
  url: string
  status: string
  title: string | null
}

interface TaskProgressPayload {
  task_id?: string
  status?: string
  url?: string
  title?: string | null
}

const PAGE_TITLE = '最近任务'
const EMPTY_TITLE = '还没有任务'
const EMPTY_HINT = '去输入页粘贴一个链接开始'
const GOTO_INPUT_LABEL = '前往输入页'
const LOAD_ERROR_PREFIX = '加载任务失败'
const RETRY_ERROR_PREFIX = '重试失败'

const STATUS_LABELS: Record<string, string> = {
  pending: 'PENDING',
  running: 'RUNNING',
  completed: 'DONE',
  failed: 'FAILED',
}

const STACK_OPACITY_INDEX_1 = '0.95'
const STACK_OPACITY_DEFAULT = '0.9'
const STACK_OFFSET_PX = 2
const SLIDE_IN_OFFSET_PX = 20
const SLIDE_IN_OFFSET_STYLE = `${SLIDE_IN_OFFSET_PX}px`

const tasks = ref<Task[]>([])
const loadError = ref('')
const retryError = ref('')
const retryingIds = ref<Set<string>>(new Set())

let isActive = true
let unlistenProgress: UnlistenFn | null = null
const router = useRouter()

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return String(error)
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status.toUpperCase()
}

function formatSource(url: string): string {
  try {
    const { hostname } = new URL(url)
    return hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function getCardStyle(index: number): Record<string, string> {
  if (index === 0) return {}
  const offset = index * STACK_OFFSET_PX
  const opacity = index === 1 ? STACK_OPACITY_INDEX_1 : STACK_OPACITY_DEFAULT
  return {
    '--stack-offset': `${offset}px`,
    opacity,
  }
}

async function loadTasks() {
  loadError.value = ''
  try {
    const result = await invoke<{ tasks: Task[] }>('list_tasks', { limit: 50 })
    tasks.value = result.tasks || []
  } catch (error: unknown) {
    loadError.value = `${LOAD_ERROR_PREFIX}: ${getErrorMessage(error)}`
  }
}

async function retry(taskId: string) {
  retryError.value = ''
  retryingIds.value = new Set(retryingIds.value).add(taskId)
  try {
    await invoke('retry_task', { task_id: taskId })
  } catch (error: unknown) {
    retryError.value = `${RETRY_ERROR_PREFIX}: ${getErrorMessage(error)}`
  } finally {
    const next = new Set(retryingIds.value)
    next.delete(taskId)
    retryingIds.value = next
  }
}

function goToInput() {
  router.push('/input')
}

function upsertTask(payload: TaskProgressPayload) {
  const taskId = payload.task_id
  const status = payload.status
  if (!taskId || !status) return

  const existingIndex = tasks.value.findIndex((task) => task.id === taskId)
  if (existingIndex >= 0) {
    tasks.value = tasks.value.map((task, index) =>
      index === existingIndex
        ? { ...task, status, title: payload.title ?? task.title }
        : task,
    )
    return
  }

  const newTask: Task = {
    id: taskId,
    url: payload.url || '',
    status,
    title: payload.title ?? null,
  }
  tasks.value = [newTask, ...tasks.value]
}

onMounted(async () => {
  await loadTasks()
  unlistenProgress = await listen<TaskProgressPayload>('task_progress', (event) => {
    upsertTask(event.payload)
  })

  if (!isActive) {
    unlistenProgress?.()
    unlistenProgress = null
  }
})

onUnmounted(() => {
  isActive = false
  unlistenProgress?.()
})
</script>

<template>
  <div class="tasks-view">
    <header class="tasks-header">
      <h2 class="title">{{ PAGE_TITLE }}</h2>
      <span class="count">{{ tasks.length }} 条</span>
    </header>

    <div v-if="loadError || retryError" class="error-banner" role="alert">
      {{ loadError || retryError }}
    </div>

    <div v-if="tasks.length === 0" class="empty-state">
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
      <h3 class="empty-title">{{ EMPTY_TITLE }}</h3>
      <p class="empty-hint">{{ EMPTY_HINT }}</p>
      <button class="goto-input-button" @click="goToInput">
        {{ GOTO_INPUT_LABEL }}
      </button>
    </div>

    <ul v-else class="task-list">
      <li
        v-for="(task, index) in tasks"
        :key="task.id"
        class="task-card"
        :class="[task.status, { latest: index === 0 }]"
        :style="getCardStyle(index)"
      >
        <div class="card-row">
          <span class="status-indicator">
            <span class="status-dot" :class="task.status"></span>
            <span class="status-label">{{ statusLabel(task.status) }}</span>
          </span>
          <button
            v-if="task.status === 'failed'"
            class="retry-button"
            :disabled="retryingIds.has(task.id)"
            @click="retry(task.id)"
          >
            重试
          </button>
        </div>
        <p class="task-title">{{ task.title || task.url }}</p>
        <p class="task-source">{{ formatSource(task.url) }}</p>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.tasks-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  overflow: hidden;
}

.tasks-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.count {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.error-banner {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: color-mix(in srgb, var(--status-red) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--status-red) 30%, transparent);
  border-radius: var(--radius-md);
  color: var(--status-red);
  font-size: var(--text-sm);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 12px;
  padding: 24px;
  text-align: center;
}

.empty-logo {
  width: 56px;
  height: 56px;
  color: var(--text-secondary);
  opacity: 0.15;
}

.empty-title {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 500;
  color: var(--text-primary);
}

.empty-hint {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.goto-input-button {
  margin-top: 8px;
  padding: 8px 16px;
  background: var(--surface-elevated);
  border: 1px solid var(--accent-coral);
  border-radius: var(--radius-sm);
  color: var(--status-green);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.goto-input-button:hover {
  background: var(--status-green);
  color: var(--surface-bg);
}

.task-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.task-card {
  position: relative;
  padding: 14px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  transition: transform 0.3s ease, opacity 0.3s ease;
  animation: slideIn 300ms ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(calc(var(--stack-offset, 0px) - v-bind(SLIDE_IN_OFFSET_STYLE)));
  }
  to {
    opacity: 1;
    transform: translateY(var(--stack-offset, 0px));
  }
}

.task-card.running {
  animation: slideIn 300ms ease-out, pulseAmber 2s ease-in-out infinite;
}

@keyframes pulseAmber {
  0%,
  100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--status-amber) 25%, transparent);
  }
  50% {
    box-shadow: 0 0 12px 2px color-mix(in srgb, var(--status-amber) 25%, transparent);
  }
}

.task-card.failed {
  border-color: var(--status-red);
}

.card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-secondary);
}

.status-dot.pending {
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

.status-label {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.05em;
}

.task-card.running .status-label {
  color: var(--status-amber);
}

.task-card.completed .status-label {
  color: var(--status-green);
}

.task-card.failed .status-label {
  color: var(--status-red);
}

.task-title {
  margin: 0 0 4px;
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-source {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.retry-button {
  padding: 4px 10px;
  background: transparent;
  border: 1px solid var(--status-red);
  border-radius: var(--radius-sm);
  color: var(--status-red);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.retry-button:hover:not(:disabled) {
  background: var(--status-red);
  color: var(--surface-bg);
}

.retry-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (prefers-reduced-motion: reduce) {
  .task-card {
    animation: none;
  }
}
</style>
