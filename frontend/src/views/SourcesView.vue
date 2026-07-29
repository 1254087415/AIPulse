<script setup lang="ts">
/**
 * SourcesView — reads the real `/api/sources` list and renders each entry.
 *
 * Spec §6.14 / §8.1 — `/sources` must land on a dedicated View (not be
 * redirected to SettingsView). Phase 7 of the plan notes that the rich
 * source-editor UI lands later; this minimal version exists so the route
 * resolves, the panel renders real data, and console stays clean.
 */
import { onMounted, ref } from 'vue'
import PageHeader from '../components/ui/PageHeader.vue'
import { apiFetch } from '../lib/apiFetch'

interface Source {
  id: string
  name: string
  source_type: string
  collector_class: string
  default_weight: number
  fetch_interval_minutes: number
  is_active: boolean
  last_fetched_at: string | null
  last_error: string | null
}

const sources = ref<Source[]>([])
const loading = ref(false)
const errorMessage = ref('')

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await apiFetch<{ success: boolean; data: Source[] }>('/api/sources')
    sources.value = response.data
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

onMounted(load)
</script>

<template>
  <section class="sources-view" data-testid="sources-view">
    <PageHeader title="来源" subtitle="已配置的内容来源与采集器状态" />

    <p v-if="loading" class="state-line" data-testid="loading">加载中…</p>
    <p v-else-if="errorMessage" class="state-line state-error" data-testid="error">
      加载失败：{{ errorMessage }}
    </p>
    <p v-else-if="sources.length === 0" class="state-line" data-testid="empty">
      暂无来源
    </p>

    <ul v-else class="source-list" data-testid="source-list">
      <li v-for="src in sources" :key="src.id" class="source-card">
        <div class="source-card__row">
          <span class="source-card__name">{{ src.name }}</span>
          <span
            class="source-card__badge"
            :class="{ 'source-card__badge--off': !src.is_active }"
          >
            {{ src.is_active ? '启用' : '停用' }}
          </span>
        </div>
        <dl class="source-card__meta">
          <dt>类型</dt><dd>{{ src.source_type }}</dd>
          <dt>采集器</dt><dd><code>{{ src.collector_class }}</code></dd>
          <dt>权重</dt><dd>{{ src.default_weight }}</dd>
          <dt>间隔</dt><dd>{{ src.fetch_interval_minutes }} 分钟</dd>
          <dt>最近拉取</dt><dd>{{ formatTime(src.last_fetched_at) }}</dd>
          <dt v-if="src.last_error">错误</dt>
          <dd v-if="src.last_error" class="state-error">{{ src.last_error }}</dd>
        </dl>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.sources-view {
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
.source-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.source-card {
  padding: 12px 14px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}
.source-card__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.source-card__name {
  font-weight: 600;
}
.source-card__badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--status-green) 20%, transparent);
  color: var(--status-green);
}
.source-card__badge--off {
  background: color-mix(in srgb, var(--status-red) 20%, transparent);
  color: var(--status-red);
}
.source-card__meta {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 12px;
  margin: 0;
  font-size: 12px;
}
.source-card__meta dt {
  color: var(--text-secondary);
}
.source-card__meta dd {
  margin: 0;
  color: var(--text-primary);
}
</style>