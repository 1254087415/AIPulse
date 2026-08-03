<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppButton from '../../components/ui/AppButton.vue'
import PageHeader from '../../components/ui/PageHeader.vue'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import { agentApi } from '../../api/agent'
import {
  archiveHotspot,
  listHotspots,
  notifyHotspot,
  retryHotspot,
  type HotspotRecord,
  updateHotspotDecision,
} from '../../api/hotspots'
import { formatDateTime, formatStatusLabel } from '../../lib/format'

const hotspots = ref<HotspotRecord[]>([])
const loading = ref(false)
const errorMessage = ref('')
const actionLoading = ref<Record<string, string | null>>({})

const RECORD_STATUSES = 'pending,worth_learning,skipped,failed,archived,worth_notified'

function statusTone(status: string): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'archived' || status === 'worth_learning' || status === 'worth_notified') {
    return 'success'
  }
  if (status === 'pending') return 'warning'
  if (status === 'failed') return 'danger'
  return 'neutral'
}

function busyAction(hotspotId: string): string | null {
  return actionLoading.value[hotspotId] ?? null
}

function isBusy(hotspotId: string, action: string): boolean {
  return busyAction(hotspotId) === action
}

function setBusy(hotspotId: string, action: string | null): void {
  actionLoading.value = { ...actionLoading.value, [hotspotId]: action }
}

function clearBusy(hotspotId: string): void {
  const next = { ...actionLoading.value }
  delete next[hotspotId]
  actionLoading.value = next
}

function getBvid(hotspot: HotspotRecord): string {
  return hotspot.content_id || hotspot.id
}

function getNotePath(hotspot: HotspotRecord): string | null {
  return hotspot.obsidian_summary_path || hotspot.obsidian_source_path || null
}

async function loadHotspots(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    hotspots.value = await listHotspots({
      decisionStatus: RECORD_STATUSES,
      limit: 50,
      page: 1,
      sort: 'created_at',
      order: 'desc',
    })
  } catch (error: unknown) {
    hotspots.value = []
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

async function runAction(
  hotspot: HotspotRecord,
  action: string,
  task: () => Promise<unknown>,
): Promise<void> {
  errorMessage.value = ''
  setBusy(hotspot.id, action)
  try {
    await task()
    await loadHotspots()
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    clearBusy(hotspot.id)
  }
}

async function processHotspot(hotspot: HotspotRecord): Promise<void> {
  await runAction(hotspot, 'process', async () => {
    await agentApi.enqueueProcess({ bvid: getBvid(hotspot) })
  })
}

async function skipHotspot(hotspot: HotspotRecord): Promise<void> {
  await runAction(hotspot, 'skip', async () => {
    await updateHotspotDecision(hotspot.id, 'skipped')
  })
}

async function retry(hotspot: HotspotRecord): Promise<void> {
  await runAction(hotspot, 'retry', async () => {
    await retryHotspot(hotspot.id)
  })
}

async function archive(hotspot: HotspotRecord): Promise<void> {
  await runAction(hotspot, 'archive', async () => {
    await archiveHotspot(hotspot.id)
  })
}

async function notify(hotspot: HotspotRecord): Promise<void> {
  await runAction(hotspot, 'notify', async () => {
    await notifyHotspot(hotspot.id)
  })
}

function openNote(hotspot: HotspotRecord): void {
  const notePath = getNotePath(hotspot)
  if (!notePath) return
  window.location.href = `obsidian://open?path=${encodeURIComponent(notePath)}`
}

onMounted(() => void loadHotspots())
</script>

<template>
  <section class="follow-panel" data-testid="panel-follow-records" aria-labelledby="records-title">
    <PageHeader
      heading-id="records-title"
      title="处理记录"
      subtitle="按 decision_status 查看热点处理状态"
    >
      <template #actions>
        <AppButton
          size="sm"
          variant="secondary"
          :loading="loading"
          data-testid="refresh-records"
          @click="loadHotspots"
        >
          刷新
        </AppButton>
      </template>
    </PageHeader>

    <p v-if="loading" class="state-line">正在加载处理记录…</p>
    <p v-else-if="errorMessage" class="state-line state-error">{{ errorMessage }}</p>
    <p v-else-if="hotspots.length === 0" class="empty-state" data-testid="empty-state">
      暂无处理记录，新的热点会在这里显示。
    </p>

    <div v-else class="record-list" role="list">
      <article v-for="hotspot in hotspots" :key="hotspot.id" class="record-row" role="listitem">
        <div class="record-main">
          <strong :title="hotspot.title">{{ hotspot.title || hotspot.content_id || hotspot.id }}</strong>
          <span class="record-video" :title="getBvid(hotspot)">{{ getBvid(hotspot) }}</span>
        </div>

        <span class="record-up">{{ hotspot.up_name || '未知 UP 主' }}</span>

        <StatusBadge
          :tone="statusTone(hotspot.decision_status)"
          :label="formatStatusLabel(hotspot.decision_status)"
        />

        <time class="record-time" :datetime="hotspot.created_at || undefined">
          {{ formatDateTime(hotspot.created_at) }}
        </time>

        <span class="record-note" :title="getNotePath(hotspot) || ''">
          {{ getNotePath(hotspot) || '尚未生成笔记' }}
        </span>

        <div class="record-actions">
          <template v-if="hotspot.decision_status === 'pending'">
            <AppButton
              size="sm"
              variant="primary"
              :loading="isBusy(hotspot.id, 'process')"
              :data-testid="`process-${hotspot.id}`"
              @click="processHotspot(hotspot)"
            >
              AI 处理
            </AppButton>
            <AppButton
              size="sm"
              variant="danger"
              :loading="isBusy(hotspot.id, 'skip')"
              :data-testid="`skip-${hotspot.id}`"
              @click="skipHotspot(hotspot)"
            >
              跳过
            </AppButton>
          </template>

          <template
            v-else-if="
              hotspot.decision_status === 'worth_learning'
              || hotspot.decision_status === 'worth_notified'
            "
          >
            <AppButton
              size="sm"
              variant="primary"
              :loading="isBusy(hotspot.id, 'archive')"
              :data-testid="`archive-${hotspot.id}`"
              @click="archive(hotspot)"
            >
              归档到 Obsidian
            </AppButton>
            <AppButton
              size="sm"
              variant="secondary"
              :disabled="hotspot.notified || hotspot.decision_status === 'worth_notified'"
              :loading="isBusy(hotspot.id, 'notify')"
              :data-testid="`notify-${hotspot.id}`"
              @click="notify(hotspot)"
            >
              通知
            </AppButton>
          </template>

          <template v-else-if="hotspot.decision_status === 'skipped'">
            <AppButton
              size="sm"
              variant="primary"
              :loading="isBusy(hotspot.id, 'archive')"
              :data-testid="`force-archive-${hotspot.id}`"
              @click="archive(hotspot)"
            >
              强制归档
            </AppButton>
          </template>

          <template v-else-if="hotspot.decision_status === 'failed'">
            <AppButton
              size="sm"
              variant="primary"
              :loading="isBusy(hotspot.id, 'retry')"
              :data-testid="`retry-${hotspot.id}`"
              @click="retry(hotspot)"
            >
              重试
            </AppButton>
            <AppButton
              size="sm"
              variant="danger"
              :loading="isBusy(hotspot.id, 'skip')"
              :data-testid="`skip-${hotspot.id}`"
              @click="skipHotspot(hotspot)"
            >
              跳过
            </AppButton>
          </template>

          <template v-else-if="hotspot.decision_status === 'archived'">
            <AppButton size="sm" variant="secondary" disabled>已归档 ✓</AppButton>
            <AppButton
              v-if="getNotePath(hotspot)"
              size="sm"
              variant="primary"
              :data-testid="`view-note-${hotspot.id}`"
              @click="openNote(hotspot)"
            >
              查看笔记
            </AppButton>
          </template>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.follow-panel {
  padding: 24px;
}

.state-line,
.empty-state {
  padding: 24px;
  color: var(--text-secondary);
  background: var(--surface-elevated);
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-md);
}

.state-error {
  color: var(--status-red);
}

.record-list {
  display: grid;
  gap: 8px;
}

.record-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.5fr) minmax(110px, .9fr) 110px 140px minmax(170px, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 14px 16px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}

.record-main {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.record-main strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-video,
.record-up,
.record-time,
.record-note {
  color: var(--text-secondary);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-video {
  font-family: var(--font-mono);
  font-size: 11px;
  cursor: help;
}

.record-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 1100px) {
  .record-row {
    grid-template-columns: 1fr 1fr;
  }

  .record-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}

@media (max-width: 700px) {
  .record-row {
    grid-template-columns: 1fr;
  }

  .record-up,
  .record-time,
  .record-note {
    width: 100%;
  }
}
</style>
