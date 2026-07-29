<script setup lang="ts">
import { onMounted, ref } from 'vue'
import SummarizeButton from '../../components/buttons/SummarizeButton.vue'
import AppButton from '../../components/ui/AppButton.vue'
import PageHeader from '../../components/ui/PageHeader.vue'
import { formatDateTime } from '../../lib/format'
import { listPendingHotspots, type Hotspot } from '../../api/summaryJobs'

const hotspots = ref<Hotspot[]>([])
const loading = ref(false)
const errorMessage = ref('')

async function loadHotspots(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    hotspots.value = await listPendingHotspots()
  } catch (error: unknown) {
    hotspots.value = []
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

onMounted(() => void loadHotspots())
</script>

<template>
  <section class="follow-panel" data-testid="panel-follow-upcoming" aria-labelledby="upcoming-title">
    <PageHeader heading-id="upcoming-title" title="即将学习" subtitle="已扫描、等待生成摘要的待学习视频">
      <template #actions>
        <AppButton
          size="sm"
          variant="secondary"
          :loading="loading"
          data-testid="refresh-upcoming"
          @click="loadHotspots"
        >
          刷新
        </AppButton>
      </template>
    </PageHeader>
    <p v-if="loading" class="state-line">正在加载待学习内容…</p>
    <p v-else-if="errorMessage" class="state-line state-error">暂时无法读取待学习内容。</p>
    <p v-else-if="hotspots.length === 0" class="empty-state" data-testid="empty-state">
      当前没有待学习内容。新的关注视频出现后会自动加入这里。
    </p>
    <div v-else class="item-list" role="list">
      <article v-for="hotspot in hotspots" :key="hotspot.id" class="item-row" role="listitem">
        <div class="item-copy">
          <strong>{{ hotspot.title || hotspot.content_id || hotspot.id }}</strong>
          <span>{{ hotspot.up_name || hotspot.source || '未知来源' }}</span>
        </div>
        <span class="item-time">{{ formatDateTime(hotspot.created_at) }}</span>
        <SummarizeButton :bvid="hotspot.content_id || hotspot.video_id || hotspot.id" />
      </article>
    </div>
  </section>
</template>

<style scoped>
.follow-panel { padding: 24px; }
.state-line, .empty-state { padding: 24px; color: var(--text-secondary); background: var(--surface-elevated); border: 1px dashed var(--border-subtle); border-radius: var(--radius-md); }
.state-error { color: var(--status-red); }
.item-list { display: grid; gap: 8px; }
.item-row { display: grid; grid-template-columns: 1fr 180px auto; gap: 16px; align-items: center; padding: 16px; background: var(--surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
.item-copy { display: grid; gap: 4px; min-width: 0; }
.item-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-copy span, .item-time { color: var(--text-secondary); font-size: 12px; }
@media (max-width: 700px) { .item-row { grid-template-columns: 1fr auto; } .item-time { grid-column: 1; } }
</style>
