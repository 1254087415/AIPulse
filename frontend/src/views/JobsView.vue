<script setup lang="ts">
/**
 * JobsView — 定时任务列表（spec §6.14 / §8.1）。
 *
 * 数据来源：GET /api/scheduler/jobs
 * 真实返回字段：id / name / func / trigger / next_run_time
 */
import { onMounted, ref } from 'vue'
import PageHeader from '../components/ui/PageHeader.vue'
import { apiFetch } from '../lib/apiFetch'

interface ScheduledJob {
  id: string
  name: string
  func: string
  trigger: string
  next_run_time: string | null
}

const jobs = ref<ScheduledJob[]>([])
const loading = ref(false)
const errorMessage = ref('')

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await apiFetch<{ success: boolean; data: ScheduledJob[] }>(
      '/api/scheduler/jobs',
    )
    jobs.value = response.data
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

onMounted(load)
</script>

<template>
  <section class="jobs-view" data-testid="jobs-view">
    <PageHeader title="定时任务" subtitle="调度器注册的任务与下次运行时间" />

    <p v-if="loading" class="state-line" data-testid="loading">加载中…</p>
    <p v-else-if="errorMessage" class="state-line state-error" data-testid="error">
      加载失败：{{ errorMessage }}
    </p>
    <p v-else-if="jobs.length === 0" class="state-line" data-testid="empty">
      暂无任务
    </p>

    <ul v-else class="job-list" data-testid="job-list">
      <li v-for="job in jobs" :key="job.id" class="job-row" data-testid="job-row">
        <div class="job-row__head">
          <span class="job-row__name">{{ job.name }}</span>
          <span class="job-row__trigger">{{ job.trigger }}</span>
        </div>
        <code class="job-row__func">{{ job.func }}</code>
        <div class="job-row__meta">
          <span class="job-row__time">下次运行：{{ formatTime(job.next_run_time) }}</span>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.jobs-view {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}
.view-title {
  margin: 0 0 4px;
  font-size: var(--text-xl);
  font-weight: 600;
}
.state-line {
  margin: 16px 0;
  font-size: 14px;
  color: var(--text-secondary);
}
.state-error {
  color: var(--status-red);
}
.job-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.job-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
}
.job-row__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.job-row__name {
  font-weight: 500;
  color: var(--text-primary);
}
.job-row__trigger {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: var(--surface-bg);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  font-family: var(--font-mono);
}
.job-row__func {
  font-size: 12px;
  color: var(--text-secondary);
  word-break: break-all;
  font-family: var(--font-mono);
}
.job-row__meta {
  margin-top: 4px;
}
.job-row__time {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>