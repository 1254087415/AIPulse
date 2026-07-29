<script setup lang="ts">
/**
 * SourcesView — reads the real `/api/sources` list and renders each entry.
 *
 * Spec §6.14 / §8.1 — `/sources` must land on a dedicated View (not be
 * redirected to SettingsView). Phase 7 of the plan notes that the rich
 * source-editor UI lands later; this minimal version exists so the route
 * resolves, the panel renders real data, and console stays clean.
 */
import { computed, onMounted, ref } from 'vue'
import PageHeader from '../components/ui/PageHeader.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { apiFetch } from '../lib/apiFetch'
import { formatDateTime, formatInterval } from '../lib/format'
import {
  summarizeClassPath,
  summarizeError,
  type ErrorSummary,
  type TechnicalSummary,
} from '../lib/errorMessage'

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

interface SourceView {
  source: Source
  collector: TechnicalSummary
  error: ErrorSummary
}

const sources = ref<SourceView[]>([])
const loading = ref(false)
const errorMessage = ref('')

function viewSource(src: Source): SourceView {
  return {
    source: src,
    collector: summarizeClassPath(src.collector_class),
    error: summarizeError(src.last_error),
  }
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await apiFetch<{ success: boolean; data: Source[] }>('/api/sources')
    sources.value = response.data.map(viewSource)
  } catch (error: unknown) {
    sources.value = []
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

const fallbackError = computed(() => summarizeError(errorMessage.value))

onMounted(load)
</script>

<template>
  <section class="sources-view" data-testid="sources-view">
    <PageHeader title="来源" subtitle="已配置的内容来源与采集器状态" />

    <p v-if="loading" class="state-line" data-testid="loading">加载中…</p>
    <p
      v-else-if="errorMessage"
      class="state-line state-error"
      data-testid="error"
      :title="fallbackError.technical ?? fallbackError.summary"
    >
      {{ fallbackError.summary }}
    </p>
    <p v-else-if="sources.length === 0" class="state-line" data-testid="empty">
      暂无来源
    </p>

    <ul v-else class="source-list" data-testid="source-list">
      <li v-for="view in sources" :key="view.source.id" class="source-card" data-testid="source-card">
        <div class="source-card__row">
          <span class="source-card__name">{{ view.source.name }}</span>
          <StatusBadge
            :tone="view.source.is_active ? 'success' : 'neutral'"
            :label="view.source.is_active ? '启用' : '停用'"
          />
        </div>
        <dl class="source-card__meta">
          <dt>类型</dt><dd>{{ view.source.source_type }}</dd>
          <dt>采集器</dt>
          <dd>
            <span
              class="source-card__collector"
              :data-testid="`source-collector-${view.source.id}`"
              :title="view.collector.technical"
            >{{ view.collector.display }}</span>
          </dd>
          <dt>权重</dt><dd>{{ view.source.default_weight }}</dd>
          <dt>间隔</dt><dd>{{ formatInterval(view.source.fetch_interval_minutes) }}</dd>
          <dt>最近拉取</dt><dd>{{ formatDateTime(view.source.last_fetched_at) }}</dd>
          <template v-if="view.source.last_error">
            <dt>错误</dt>
            <dd
              class="state-error source-card__error"
              :data-testid="`source-error-${view.source.id}`"
              :title="view.error.technical ?? view.error.summary"
            >{{ view.error.summary }}</dd>
          </template>
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
  min-width: 0;
  overflow: hidden;
}
.source-card__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  gap: 8px;
}
.source-card__name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.source-card__meta {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
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
  overflow-wrap: anywhere;
  min-width: 0;
}
.source-card__collector {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-primary);
  overflow-wrap: anywhere;
  word-break: break-all;
}
.source-card__error {
  background: color-mix(in srgb, var(--status-red) 12%, transparent);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  overflow-wrap: anywhere;
}
</style>