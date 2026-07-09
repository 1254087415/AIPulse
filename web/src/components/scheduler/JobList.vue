<script setup lang="ts">
import type { Job } from '../../types'

const props = defineProps<{ jobs: Job[]; running: Record<string, boolean> }>()
const emit = defineEmits<{ (e: 'run', jobId: string): void }>()

function formatTime(value: string | null): string {
  if (!value) return '无'
  return new Date(value).toLocaleString('zh-CN')
}
</script>

<template>
  <ul class="job-list">
    <li v-for="job in props.jobs" :key="job.id" class="job">
      <div class="info">
        <strong>{{ job.name }}</strong>
        <span class="trigger">{{ job.trigger }}</span>
      </div>
      <div class="next-run">下次运行：{{ formatTime(job.next_run_time) }}</div>
      <button
        :disabled="props.running[job.id]"
        @click="emit('run', job.id)"
      >
        {{ props.running[job.id] ? '执行中...' : '立即执行' }}
      </button>
    </li>
  </ul>
</template>

<style scoped>
.job-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.job {
  padding: 0.75rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  margin-bottom: 0.5rem;
}
.info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.trigger {
  font-size: 0.75rem;
  color: #6b7280;
}
.next-run {
  font-size: 0.875rem;
  color: #4b5563;
  margin: 0.25rem 0;
}
button {
  padding: 0.375rem 0.75rem;
  font-size: 0.875rem;
}
</style>
