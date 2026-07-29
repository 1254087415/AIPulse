<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import SummarizeButton from '../../components/buttons/SummarizeButton.vue'
import AppButton from '../../components/ui/AppButton.vue'
import PageHeader from '../../components/ui/PageHeader.vue'
import { listSummaryJobs, type SummaryJob } from '../../api/summaryJobs'
import { subscribeSse } from '../../lib/sse-client'
import { summarizeError, type ErrorSummary } from '../../lib/errorMessage'

const jobs = ref<SummaryJob[]>([])
const loading = ref(false)
const errorMessage = ref('')
let cleanup: (() => void) | null = null

function jobErrorView(raw: string | null | undefined): ErrorSummary {
  return summarizeError(raw ?? '处理未完成，请重试')
}

function jobErrorTitle(raw: string | null | undefined): string {
  const view = summarizeError(raw ?? '处理未完成，请重试')
  return view.technical ?? view.summary
}

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

const fallbackErrorView = computed(() => summarizeError(errorMessage.value))
</script>

<template>
  <section class="follow-panel" data-testid="panel-follow-failed" aria-labelledby="failed-title">
    <PageHeader heading-id="failed-title" title="失败" subtitle="需要重试或人工处理的任务">
      <template #actions>
        <AppButton
          size="sm"
          variant="secondary"
          :loading="loading"
          data-testid="refresh-failed"
          @click="loadFailedJobs"
        >
          刷新
        </AppButton>
      </template>
    </PageHeader>
    <p v-if="loading" class="state-line">正在加载失败记录…</p>
    <p
      v-else-if="errorMessage"
      class="state-line state-error"
      :title="fallbackErrorView.technical ?? fallbackErrorView.summary"
    >
      {{ fallbackErrorView.summary }}
    </p>
    <p v-else-if="jobs.length === 0" class="empty-state" data-testid="empty-state">
      太好了，目前没有失败任务。
    </p>
    <div v-else class="item-list" role="list">
      <article v-for="job in jobs" :key="job.id" class="item-row" role="listitem">
        <div class="item-copy">
          <strong>{{ job.title || job.video_id }}</strong>
          <span>{{ job.video_id }} · {{ job.up_name || '未知 UP 主' }}</span>
          <span
            class="error-text"
            :data-testid="`failed-error-${job.id}`"
            :title="jobErrorTitle(job.error)"
          >{{ jobErrorView(job.error).summary }}</span>
        </div>
        <SummarizeButton :bvid="job.video_id" />
      </article>
    </div>
  </section>
</template>

<style scoped>
.follow-panel { padding: 24px; }
.state-line, .empty-state { padding: 24px; color: var(--text-secondary); background: var(--surface-elevated); border: 1px dashed var(--border-subtle); border-radius: var(--radius-md); }
.state-error, .error-text { color: var(--status-red); }
.item-list { display: grid; gap: 8px; }
.item-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 16px; background: var(--surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
.item-copy { display: grid; gap: 4px; min-width: 0; }
.item-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-copy span { color: var(--text-secondary); font-size: 12px; }
.item-copy .error-text { color: var(--status-red); overflow-wrap: anywhere; }
</style>
