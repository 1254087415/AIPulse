<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery, useMutation } from '@tanstack/vue-query'
import { fetchHotspot, fetchRelatedHotspots, archiveHotspot } from '../api/hotspots'
import HotspotList from '../components/hotspot/HotspotList.vue'
import { formatDateTime } from '../lib/format'
import { isSafeUrl } from '../lib/url'

const route = useRoute()
const router = useRouter()
const hotspotId = computed(() => route.params.id as string)
const hasValidId = computed(() => !!hotspotId.value)

const { data: hotspot, isLoading, error } = useQuery({
  queryKey: ['hotspot', hotspotId],
  queryFn: () => fetchHotspot(hotspotId.value),
  enabled: !!hotspotId.value,
})
const { data: related } = useQuery({
  queryKey: ['hotspot', hotspotId, 'related'],
  queryFn: () => fetchRelatedHotspots(hotspotId.value),
  enabled: !!hotspotId.value,
})
const archive = useMutation({
  mutationFn: () => archiveHotspot(hotspotId.value),
})

const safeUrl = computed(() => (hotspot.value?.data.url && isSafeUrl(hotspot.value.data.url) ? hotspot.value.data.url : null))
</script>

<template>
  <div class="page">
    <button type="button" class="back" aria-label="返回热点列表" @click="router.back()">← 返回热点列表</button>

    <div v-if="isLoading" class="state state-loading" role="status" aria-live="polite">
      正在同步信号…
    </div>

    <div v-else-if="error" class="state state-error" role="alert" aria-live="polite">
      热点详情加载失败：{{ error?.message }}
    </div>

    <div v-else-if="!hasValidId" class="state state-error" role="alert" aria-live="polite">
      热点 ID 不能为空
    </div>

    <article v-else-if="hotspot" class="detail">
      <header class="detail-header">
        <div class="detail-titles">
          <h1>{{ hotspot.data.title }}</h1>
          <div class="detail-meta">
            <span class="tag">{{ hotspot.data.source_type }}</span>
            <span v-if="hotspot.data.category" class="tag">{{ hotspot.data.category }}</span>
            <span class="tag" :class="{ 'tag-signal': hotspot.data.importance === 'high' }">
              {{ hotspot.data.importance }}
            </span>
            <time class="mono slate">{{ formatDateTime(hotspot.data.published_at, '未知时间') }}</time>
          </div>
        </div>
        <div class="detail-score">
          <span class="score-value">{{ hotspot.data.heat_score.toFixed(1) }}</span>
          <span class="score-label">热度</span>
        </div>
      </header>

      <div class="detail-body panel">
        <p v-if="hotspot.data.summary" class="summary">{{ hotspot.data.summary }}</p>
        <p v-else class="summary-empty">暂无摘要</p>
        <a
          v-if="safeUrl"
          :href="safeUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="external-link"
        >
          访问原始链接 →
        </a>
        <span v-else class="external-link disabled">链接不可用</span>
      </div>

      <div class="detail-actions">
        <button
          type="button"
          class="btn"
          :disabled="archive.isPending.value"
          @click="archive.mutate()"
        >
          {{ archive.isPending.value ? '归档中…' : '归档到 Obsidian' }}
        </button>
        <span v-if="archive.isSuccess.value" class="archive-hint" role="status" aria-live="polite">已归档</span>
      </div>

      <div v-if="archive.error.value" class="state state-error" role="alert" aria-live="polite">
        归档失败：{{ archive.error.value?.message }}
      </div>

      <section v-if="related && related.data.length > 0" class="related">
        <h2>相关热点</h2>
        <HotspotList :hotspots="related.data" />
      </section>
    </article>
  </div>
</template>

<style scoped>
.back {
  appearance: none;
  background: transparent;
  border: none;
  font-size: 14px;
  color: var(--slate);
  cursor: pointer;
  padding: 0;
  margin-bottom: 16px;
  transition: color 0.12s ease;
}

.back:hover {
  color: var(--ink);
}

.back:focus-visible {
  outline: none;
  color: var(--ink);
  box-shadow: 0 0 0 3px rgba(var(--signal-rgb), 0.18);
  border-radius: var(--radius-sm);
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--mist);
}

.detail-titles {
  min-width: 0;
}

.detail-titles h1 {
  font-size: 26px;
  margin-bottom: 10px;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.detail-score {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex-shrink: 0;
}

.score-value {
  font-family: var(--font-mono);
  font-size: 36px;
  font-weight: 700;
  color: var(--signal);
  line-height: 1;
}

.score-label {
  font-size: 11px;
  color: var(--slate);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.detail-body {
  margin-bottom: 16px;
}

.summary {
  font-size: 16px;
  line-height: 1.7;
  color: var(--ink);
  margin-bottom: 16px;
}

.summary-empty {
  font-size: 15px;
  color: var(--slate);
  margin-bottom: 16px;
}

.external-link {
  font-size: 14px;
  color: var(--signal);
}

.external-link.disabled {
  color: var(--slate);
  cursor: not-allowed;
}

.detail-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}

.archive-hint {
  font-size: 13px;
  color: var(--signal);
}

.related h2 {
  font-size: 20px;
  margin-bottom: 14px;
}

@media (max-width: 640px) {
  .detail-header {
    flex-direction: column;
  }

  .detail-score {
    flex-direction: row;
    align-items: baseline;
    gap: 8px;
  }
}
</style>
