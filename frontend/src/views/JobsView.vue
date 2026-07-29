<script setup lang="ts">
/**
 * JobsView — 定时任务列表（spec §6.14 / §8.1）。
 *
 * 数据来源：GET /api/scheduler/jobs
 * 真实返回字段：id / name / func / trigger / next_run_time
 */
import { computed, onMounted, ref } from 'vue'
import PageHeader from '../components/ui/PageHeader.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { apiFetch } from '../lib/apiFetch'
import { formatDateTime, formatJobName } from '../lib/format'
import {
  summarizeFuncPath,
  summarizeTrigger,
  summarizeError,
  type TechnicalSummary,
} from '../lib/errorMessage'

interface ScheduledJob {
  id: string
  name: string
  func: string
  trigger: string
  next_run_time: string | null
}

interface JobView {
  job: ScheduledJob
  triggerLabel: string
  func: TechnicalSummary
}

const jobs = ref<JobView[]>([])
const loading = ref(false)
const errorMessage = ref('')

function viewJob(job: ScheduledJob): JobView {
  return {
    job,
    triggerLabel: summarizeTrigger(job.trigger),
    func: summarizeFuncPath(job.func),
  }
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await apiFetch<{ success: boolean; data: ScheduledJob[] }>(
      '/api/scheduler/jobs',
    )
    jobs.value = response.data.map(viewJob)
  } catch (error: unknown) {
    jobs.value = []
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

const fallbackError = computed(() => summarizeError(errorMessage.value))

onMounted(load)
</script>

<template>
  <section class="jobs-view" data-testid="jobs-view">
    <PageHeader title="定时任务" subtitle="调度器注册的任务与下次运行时间" />

    <p v-if="loading" class="state-line" data-testid="loading">加载中…</p>
    <p
      v-else-if="errorMessage"
      class="state-line state-error"
      data-testid="error"
      :title="fallbackError.technical ?? fallbackError.summary"
    >
      {{ fallbackError.summary }}
    </p>
    <p v-else-if="jobs.length === 0" class="state-line" data-testid="empty">
      暂无任务
    </p>

    <ul v-else class="job-list" data-testid="job-list">
      <li v-for="view in jobs" :key="view.job.id" class="job-row" data-testid="job-row">
        <div class="job-row__head">
          <span class="job-row__name">{{ formatJobName(view.job.name) }}</span>
          <StatusBadge
            tone="neutral"
            :label="view.triggerLabel"
            :data-testid="`job-trigger-${view.job.id}`"
            :title="view.job.trigger"
          />
        </div>
        <span
          class="job-row__func"
          :data-testid="`job-func-${view.job.id}`"
          :title="view.func.technical"
        >{{ view.func.display }}</span>
        <div class="job-row__meta">
          <span class="job-row__time">下次运行：{{ formatDateTime(view.job.next_run_time) }}</span>
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
  min-width: 0;
}
.job-row__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.job-row__name {
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.job-row__func {
  font-size: 12px;
  color: var(--text-secondary);
  word-break: break-all;
  overflow-wrap: anywhere;
  font-family: var(--font-mono);
  cursor: help;
}
.job-row__meta {
  margin-top: 4px;
}
.job-row__time {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>