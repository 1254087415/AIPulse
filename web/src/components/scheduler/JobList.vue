<script setup lang="ts">
import type { Job } from '../../types'
import type { SchedulerLog } from '../../api/scheduler'

const props = defineProps<{
  jobs: Job[]
  running: Record<string, boolean>
  logs?: SchedulerLog[]
}>()
const emit = defineEmits<{
  (e: 'run', jobId: string): void
  (e: 'pause', jobId: string): void
  (e: 'resume', jobId: string): void
}>()

function formatTime(value: string | null): string {
  if (!value) return '无'
  return new Date(value).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="job-sections">
    <ul class="job-list" role="list">
      <li v-for="job in props.jobs" :key="job.id" class="job panel">
        <div class="job-main">
          <strong class="job-name">{{ job.name }}</strong>
          <span class="tag mono">{{ job.trigger }}</span>
        </div>
        <div class="job-next mono">
          下次运行：{{ formatTime(job.next_run_time) }}
        </div>
        <div class="job-actions">
          <button
            type="button"
            class="btn btn-ghost"
            :disabled="props.running[job.id]"
            @click="emit('run', job.id)"
          >
            {{ props.running[job.id] ? '执行中…' : '立即执行' }}
          </button>
          <button
            type="button"
            class="btn btn-ghost"
            @click="emit('pause', job.id)"
          >
            暂停
          </button>
          <button
            type="button"
            class="btn btn-ghost"
            @click="emit('resume', job.id)"
          >
            恢复
          </button>
        </div>
      </li>
    </ul>

    <section v-if="props.logs && props.logs.length > 0" class="log-section">
      <h2 class="section-title">最近执行记录</h2>
      <ul class="log-list" role="list">
        <li
          v-for="log in props.logs"
          :key="log.id"
          class="log-item"
          :class="{ 'log-error': log.status === 'error' }"
        >
          <span class="log-job">{{ log.job_id }}</span>
          <span class="tag" :class="{ 'tag-signal': log.status === 'error' }">{{ log.status }}</span>
          <time class="log-time">{{ formatTime(log.finished_at) }}</time>
          <p v-if="log.exception" class="log-exception">{{ log.exception }}</p>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.job-sections {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.job-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.job {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 8px 16px;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

.job:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.job-main {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.job-name {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
}

.job-next {
  grid-column: 1 / -1;
  font-size: 12px;
  color: var(--slate);
  letter-spacing: 0.01em;
}

.job-actions {
  grid-column: 2;
  grid-row: 1;
  display: flex;
  gap: 6px;
}

.section-title {
  font-size: 18px;
  margin-bottom: 12px;
}

.log-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--mist);
  border-radius: var(--radius-md);
  background: rgba(252, 250, 248, 0.92);
  font-size: 13px;
}

.log-error {
  border-color: rgba(217, 48, 37, 0.16);
  background: var(--signal-soft);
}

.log-job {
  font-family: var(--font-mono);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-time {
  font-size: 11px;
  color: var(--slate);
}

.log-exception {
  grid-column: 1 / -1;
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--signal);
}

@media (max-width: 640px) {
  .job {
    grid-template-columns: 1fr;
  }

  .job-actions,
  .job-next {
    grid-column: 1;
    grid-row: auto;
  }

  .job-actions {
    justify-content: flex-end;
  }
}
</style>
