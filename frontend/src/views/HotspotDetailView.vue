<script setup lang="ts">
/**
 * HotspotDetailView — reads the real `/api/hotspots/{id}` payload.
 *
 * Spec §6.14 / §8.1. Phase 4 enriches this with the three-way archive
 * controls; for now we render the real data so the route resolves without
 * errors.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiFetch } from '../lib/apiFetch'
import { safeHref } from '../lib/safeUrl'

interface Hotspot {
  id: string
  title?: string | null
  url?: string | null
  source?: string | null
  summary?: string | null
  status?: string | null
  decision_status?: string | null
  created_at?: string | null
  archived_at?: string | null
}

const route = useRoute()
const hotspotId = computed<string>(() => String(route.params.id ?? ''))

const hotspot = ref<Hotspot | null>(null)
const loading = ref(false)
const errorMessage = ref('')

let loadToken = 0

async function load(id: string): Promise<void> {
  const token = ++loadToken
  loading.value = true
  errorMessage.value = ''
  hotspot.value = null
  try {
    const response = await apiFetch<{ success: boolean; data: Hotspot }>(
      `/api/hotspots/${encodeURIComponent(id)}`,
    )
    if (token !== loadToken) return
    hotspot.value = response.data
  } catch (error: unknown) {
    if (token !== loadToken) return
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    if (token === loadToken) loading.value = false
  }
}

const safeUrl = computed<string | null>(() => safeHref(hotspot.value?.url))

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

onMounted(() => void load(hotspotId.value))
watch(() => hotspotId.value, (next) => void load(next))
</script>

<template>
  <section class="hotspot-detail-view" data-testid="hotspot-detail-view">
    <header class="view-header">
      <h2 class="view-title">热点详情</h2>
      <p class="view-banner">该视图将在 Phase 4 完整实现（当前仅展示真实数据）</p>
    </header>

    <p v-if="loading" class="state-line" data-testid="loading">加载中…</p>
    <p v-else-if="errorMessage" class="state-line state-error" data-testid="error">
      加载失败：{{ errorMessage }}
    </p>
    <p v-else-if="!hotspot" class="state-line" data-testid="empty">
      未找到 ID 为 {{ hotspotId }} 的热点
    </p>

    <article v-else class="hotspot-card">
      <h3 class="hotspot-card__title">{{ hotspot.title || hotspot.id }}</h3>
      <dl class="hotspot-card__meta">
        <dt>来源</dt><dd>{{ hotspot.source || '—' }}</dd>
        <dt>状态</dt><dd>{{ hotspot.status || hotspot.decision_status || '—' }}</dd>
        <dt>URL</dt>
        <dd>
          <a v-if="safeUrl" :href="safeUrl" target="_blank" rel="noopener noreferrer">
            {{ hotspot.url }}
          </a>
          <span v-else>{{ hotspot.url || '—' }}</span>
        </dd>
        <dt>创建时间</dt><dd>{{ formatTime(hotspot.created_at) }}</dd>
        <dt>归档时间</dt><dd>{{ formatTime(hotspot.archived_at) }}</dd>
      </dl>
      <p v-if="hotspot.summary" class="hotspot-card__summary">{{ hotspot.summary }}</p>
    </article>
  </section>
</template>

<style scoped>
.hotspot-detail-view {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}
.view-title {
  margin: 0 0 4px;
  font-size: var(--text-xl);
  font-weight: 600;
}
.view-banner {
  margin: 0 0 16px;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface-elevated);
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-sm);
  display: inline-block;
}
.state-line {
  margin: 16px 0;
  font-size: 14px;
  color: var(--text-secondary);
}
.state-error {
  color: var(--status-red);
}
.hotspot-card {
  padding: 16px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}
.hotspot-card__title {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 600;
}
.hotspot-card__meta {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 14px;
  margin: 0 0 12px;
  font-size: 13px;
}
.hotspot-card__meta dt {
  color: var(--text-secondary);
}
.hotspot-card__meta dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.hotspot-card__summary {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}
</style>