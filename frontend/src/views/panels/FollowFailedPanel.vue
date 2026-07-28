<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import SummarizeButton from '../../components/buttons/SummarizeButton.vue'
import { listSummaryJobs, type SummaryJob } from '../../api/summaryJobs'
import { subscribeSse } from '../../lib/sse-client'

const jobs = ref<SummaryJob[]>([])
const loading = ref(false)
const errorMessage = ref('')
let cleanup: (() => void) | null = null

async function loadFailedJobs(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const records = await listSummaryJobs({ limit: 20 })
    jobs.value = records.filter(
      (job) => job.status === 'failed' || job.status === 'partial' || job.status === 'timeout',
    )
  } catch (error: unknown) {
    jobs.value = []
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadFailedJobs()
  cleanup = subscribeSse('/api/summary/events', [
    { event: 'failed', handler: () => void loadFailedJobs() },
    { event: 'partial', handler: () => void loadFailedJobs() },
    { event: 'timeout', handler: () => void loadFailedJobs() },
  ])
})

onBeforeUnmount(() => cleanup?.())
</script>

<template>
  <section class="follow-panel" data-testid="panel-follow-failed" aria-labelledby="failed-title">
    <header class="panel-header">
      <div>
        <p class="eyebrow">ACTION REQUIRED</p>
        <h2 id="failed-title">失败</h2>
      </div>
      <button type="button" class="refresh-button" :disabled="loading" @click="loadFailedJobs">刷新</button>
    </header>
    <p v-if="loading" class="state-line">正在加载失败记录…</p>
    <p v-else-if="errorMessage" class="state-line state-error">暂时无法读取失败记录。</p>
    <p v-else-if="jobs.length === 0" class="empty-state" data-testid="empty-state">
      太好了，目前没有失败任务。
    </p>
    <div v-else class="item-list" role="list">
      <article v-for="job in jobs" :key="job.id" class="item-row" role="listitem">
        <div class="item-copy">
          <strong>{{ job.title || job.video_id }}</strong>
          <span>{{ job.video_id }} · {{ job.up_name || '未知 UP 主' }}</span>
          <span class="error-text">{{ job.error || '处理未完成，请重试' }}</span>
        </div>
        <SummarizeButton :bvid="job.video_id" />
      </article>
    </div>
  </section>
</template>

<style scoped>
.follow-panel { padding: 24px; }
.panel-header { display: flex; justify-content: space-between; align-items: start; gap: 16px; margin-bottom: 20px; }
.eyebrow { margin: 0 0 4px; color: var(--text-secondary); font-size: 11px; letter-spacing: .12em; }
h2 { margin: 0; font-size: var(--text-xl); }
.refresh-button { border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); background: var(--surface-elevated); padding: 7px 12px; cursor: pointer; }
.refresh-button:disabled { opacity: .6; cursor: default; }
.state-line, .empty-state { padding: 24px; color: var(--text-secondary); background: var(--surface-elevated); border: 1px dashed var(--border-subtle); border-radius: var(--radius-md); }
.state-error, .error-text { color: var(--status-red); }
.item-list { display: grid; gap: 8px; }
.item-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 16px; background: var(--surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
.item-copy { display: grid; gap: 4px; min-width: 0; }
.item-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-copy span { color: var(--text-secondary); font-size: 12px; }
.item-copy .error-text { color: var(--status-red); overflow-wrap: anywhere; }
</style>
