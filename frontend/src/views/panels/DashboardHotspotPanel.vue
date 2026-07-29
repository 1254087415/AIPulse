<script setup lang="ts">
import { onMounted, ref } from 'vue'
import PageHeader from '../../components/ui/PageHeader.vue'
import { apiFetch } from '../../lib/apiFetch'

interface Hotspot {
  id: string
  title: string
  summary: string | null
  source_type: string
  heat_score: number
  importance: string
  category: string | null
  published_at: string | null
}

interface HotspotResponse {
  success: boolean
  data: Hotspot[]
  meta: { total: number; page: number; limit: number }
}

const hotspots = ref<Hotspot[]>([])
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')

function formatTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await apiFetch<HotspotResponse>('/api/hotspots', {
      query: { page: '1', limit: '20', sort: 'published_at', order: 'desc' },
    })
    hotspots.value = response.data
    total.value = response.meta.total
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="dashboard-hotspot-panel" data-testid="panel-hotspot">
    <PageHeader title="AI 热点" subtitle="按发布时间展示最新信号">
      <template #actions>
        <span
          v-if="!loading && !errorMessage"
          class="dashboard-hotspot-panel__count"
        >
          {{ total }} 条
        </span>
      </template>
    </PageHeader>

    <p v-if="loading" class="state-line" data-testid="loading">加载中…</p>
    <p v-else-if="errorMessage" class="state-line state-error" data-testid="error">
      加载失败：{{ errorMessage }}
    </p>
    <p v-else-if="hotspots.length === 0" class="state-line" data-testid="empty">
      暂无热点
    </p>

    <ul v-else class="hotspot-list" data-testid="hotspot-list">
      <li v-for="hotspot in hotspots" :key="hotspot.id" class="hotspot-card">
        <div class="hotspot-card__header">
          <h3>{{ hotspot.title }}</h3>
          <span class="hotspot-card__score">热度 {{ hotspot.heat_score.toFixed(1) }}</span>
        </div>
        <p v-if="hotspot.summary" class="hotspot-card__summary">{{ hotspot.summary }}</p>
        <div class="hotspot-card__meta">
          <span>{{ hotspot.source_type }}</span>
          <span>{{ hotspot.importance }}</span>
          <span v-if="hotspot.category">{{ hotspot.category }}</span>
          <time>{{ formatTime(hotspot.published_at) }}</time>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.dashboard-hotspot-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hotspot-card__header,
.hotspot-card__meta {
  display: flex;
  align-items: center;
}

.hotspot-card h3 {
  margin: 0;
  color: var(--text-primary);
}

.dashboard-hotspot-panel__count,
.hotspot-card__score {
  color: var(--accent-coral);
  font-family: var(--font-mono);
  font-size: 12px;
}

.state-line {
  margin: 0;
  padding: 16px;
  color: var(--text-secondary);
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}

.state-error {
  color: var(--status-red);
}

.hotspot-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.hotspot-card {
  padding: 14px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}

.hotspot-card__header {
  justify-content: space-between;
  gap: 12px;
}

.hotspot-card h3 {
  font-size: 15px;
}

.hotspot-card__summary {
  margin: 10px 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.hotspot-card__meta {
  flex-wrap: wrap;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 11px;
}
</style>
