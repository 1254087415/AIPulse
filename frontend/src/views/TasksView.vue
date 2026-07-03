<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
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

const tasks = ref<Task[]>([])
const retryError = ref('')

let isUnmounted = false
let unlisten: UnlistenFn | null = null

async function retry(taskId: string) {
  retryError.value = ''
  try {
    await invoke('retry_task', { taskId })
  } catch (e) {
    retryError.value = `重试失败: ${e}`
    // eslint-disable-next-line no-console
    console.error(e)
  }
}

onMounted(async () => {
  const fn = await listen<TaskProgressPayload>('task_progress', (event) => {
    const payload = event.payload
    if (!payload.task_id || !payload.status) return

    const existing = tasks.value.find((t) => t.id === payload.task_id)
    if (existing) {
      existing.status = payload.status
      if (payload.title) existing.title = payload.title
    } else {
      tasks.value.unshift({
        id: payload.task_id,
        url: payload.url || '',
        status: payload.status,
        title: payload.title || null,
      })
    }
  })
  if (isUnmounted) {
    fn()
  } else {
    unlisten = fn
  }
})

onUnmounted(() => {
  isUnmounted = true
  unlisten?.()
})
</script>

<template>
  <div class="tasks-container">
    <h2>最近任务</h2>
    <ul v-if="tasks.length">
      <li v-for="task in tasks" :key="task.id">
        <span class="status" :class="task.status">{{ task.status }}</span>
        <span class="title">{{ task.title || task.url }}</span>
        <button v-if="task.status === 'failed'" @click="retry(task.id)">重试</button>
      </li>
    </ul>
    <p v-else class="empty">暂无任务</p>
    <p v-if="retryError" class="error">{{ retryError }}</p>
  </div>
</template>

<style scoped>
.tasks-container {
  padding: 16px;
}

h2 {
  margin: 0 0 12px;
  font-size: 16px;
}

ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

li {
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

button {
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
</style>
