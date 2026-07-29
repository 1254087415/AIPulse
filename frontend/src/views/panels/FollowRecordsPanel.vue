<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import SummarizeButton from '../../components/buttons/SummarizeButton.vue'
import AppButton from '../../components/ui/AppButton.vue'
import PageHeader from '../../components/ui/PageHeader.vue'
import { listSummaryJobs, type SummaryJob } from '../../api/summaryJobs'
import { subscribeSse } from '../../lib/sse-client'

const jobs = ref<SummaryJob[]>([])
const loading = ref(false)
const errorMessage = ref('')
let cleanup: (() => void) | null = null

function formatTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

async function loadJobs(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    jobs.value = await listSummaryJobs({ limit: 20 })
  } catch (error: unknown) {
    jobs.value = []
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadJobs()
  cleanup = subscribeSse('/api/summary/events', [
    { event: 'completed', handler: () => void loadJobs() },
    { event: 'failed', handler: () => void loadJobs() },
    { event: 'partial', handler: () => void loadJobs() },
    { event: 'timeout', handler: () => void loadJobs() },
  ])
})

onBeforeUnmount(() => cleanup?.())
</script>

<template>
  <section class="follow-panel" data-testid="panel-follow-records" aria-labelledby="records-title">
    <PageHeader heading-id="records-title" title="处理记录" subtitle="已加入处理的视频与摘要结果">
      <template #actions>
        <AppButton
          size="sm"
          variant="secondary"
          :loading="loading"
          data-testid="refresh-records"
          @click="loadJobs"
        >
          刷新
        </AppButton>
      </template>
    </PageHeader>
    <p v-if="loading" class="state-line">正在加载处理记录…</p>
    <p v-else-if="errorMessage" class="state-line state-error">暂时无法读取处理记录。</p>
    <p v-else-if="jobs.length === 0" class="empty-state" data-testid="empty-state">
      还没有处理记录，稍后扫描到新视频后会显示在这里。
    </p>
    <div v-else class="record-list" role="list">
      <article v-for="job in jobs" :key="job.id" class="record-row" role="listitem">
        <div class="record-main">
          <strong>{{ job.title || job.video_id }}</strong>
          <span class="record-video">{{ job.video_id }}</span>
        </div>
        <span class="record-up">{{ job.up_name || '未知 UP 主' }}</span>
        <span class="status-badge" :data-status="job.status">{{ job.status }}</span>
        <time class="record-time" :datetime="job.created_at || undefined">{{ formatTime(job.created_at) }}</time>
        <span class="record-note">{{ job.note_path || '尚未生成笔记' }}</span>
        <SummarizeButton
          :bvid="job.video_id"
          :has-summary="Boolean(job.note_path)"
          :obsidian-path="job.note_path"
        />
      </article>
    </div>
  </section>
</template>

<style scoped>
.follow-panel { padding: 24px; }
.state-line, .empty-state { padding: 24px; color: var(--text-secondary); background: var(--surface-elevated); border: 1px dashed var(--border-subtle); border-radius: var(--radius-md); }
.state-error { color: var(--status-red); }
.record-list { display: grid; gap: 8px; }
.record-row { display: grid; grid-template-columns: minmax(160px, 1.5fr) minmax(100px, .8fr) 100px 150px minmax(150px, 1fr) auto; gap: 12px; align-items: center; padding: 14px 16px; background: var(--surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
.record-main { display: grid; gap: 3px; min-width: 0; }
.record-main strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.record-video, .record-up, .record-time, .record-note { color: var(--text-secondary); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-badge { font-size: 12px; text-transform: capitalize; }
@media (max-width: 900px) { .record-row { grid-template-columns: 1fr auto; } .record-up, .record-time, .record-note { grid-column: 1; } }
</style>
