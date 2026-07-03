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

const url = ref('')
const submitting = ref(false)
const message = ref('')
const progress = ref<TaskProgress>({
  task_id: '',
  status: '',
  progress_pct: 0,
  message: '',
})
const inputRef = ref<HTMLInputElement | null>(null)

let isUnmounted = false
let unlistenProgress: UnlistenFn | null = null
let unlistenComplete: UnlistenFn | null = null

async function submit() {
  const target = url.value.trim()
  if (!target) return

  submitting.value = true
  message.value = ''
  progress.value = { task_id: '', status: 'running', progress_pct: 0, message: '提交中...' }

  try {
    await invoke('submit_url', { url: target, source: 'menubar' })
    message.value = '已加入处理队列'
    url.value = ''
  } catch (e) {
    message.value = `提交失败: ${e}`
    progress.value.status = ''
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  inputRef.value?.focus()
  const progressFn = await listen<TaskProgress>('task_progress', (event) => {
    progress.value = event.payload
  })
  const completeFn = await listen<TaskCompletePayload>('task_complete', (event) => {
    if (event.payload.status === 'success') {
      message.value = event.payload.result?.title
        ? `完成: ${event.payload.result.title}`
        : '处理完成'
    } else {
      message.value = `处理失败: ${event.payload.error_message || ''}`
    }
    progress.value = { task_id: '', status: '', progress_pct: 0, message: '' }
  })
  if (isUnmounted) {
    progressFn()
    completeFn()
  } else {
    unlistenProgress = progressFn
    unlistenComplete = completeFn
  }
})

onUnmounted(() => {
  isUnmounted = true
  unlistenProgress?.()
  unlistenComplete?.()
})
</script>

<template>
  <div class="input-container">
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
    <p v-if="message" class="message">{{ message }}</p>
  </div>
</template>

<style scoped>
.input-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
}

button {
  padding: 10px 16px;
  background: #0066ff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}

button:disabled {
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
</style>
