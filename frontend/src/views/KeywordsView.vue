<script setup lang="ts">
/**
 * KeywordsView — reads the real `/api/keywords` list.
 *
 * Spec §6.14 / §8.1. Rich editing UI lands in a later phase; this minimal
 * view exists so the route resolves, real data renders, and the console
 * stays clean.
 */
import { onMounted, ref } from 'vue'
import { apiFetch } from '../lib/apiFetch'

interface Keyword {
  id: string
  name: string
  weight: number
  is_active: boolean
  last_triggered_at: string | null
}

const keywords = ref<Keyword[]>([])
const loading = ref(false)
const errorMessage = ref('')

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await apiFetch<{ success: boolean; data: Keyword[] }>('/api/keywords')
    keywords.value = response.data
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
  <section class="keywords-view" data-testid="keywords-view">
    <header class="view-header">
      <h2 class="view-title">关键词</h2>
      <p class="view-banner">该视图将在 Phase 7 完整实现（当前仅展示真实列表）</p>
    </header>

    <p v-if="loading" class="state-line" data-testid="loading">加载中…</p>
    <p v-else-if="errorMessage" class="state-line state-error" data-testid="error">
      加载失败：{{ errorMessage }}
    </p>
    <p v-else-if="keywords.length === 0" class="state-line" data-testid="empty">
      暂无关键词
    </p>

    <ul v-else class="keyword-list" data-testid="keyword-list">
      <li v-for="kw in keywords" :key="kw.id" class="keyword-row">
        <span class="keyword-row__name">{{ kw.name }}</span>
        <span class="keyword-row__weight">权重 {{ kw.weight }}</span>
        <span
          class="keyword-row__badge"
          :class="{ 'keyword-row__badge--off': !kw.is_active }"
        >
          {{ kw.is_active ? '启用' : '停用' }}
        </span>
        <span class="keyword-row__time">{{ formatTime(kw.last_triggered_at) }}</span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.keywords-view {
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
.keyword-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.keyword-row {
  display: grid;
  grid-template-columns: 1fr max-content max-content max-content;
  gap: 12px;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 14px;
}
.keyword-row__name {
  font-weight: 500;
}
.keyword-row__weight {
  color: var(--text-secondary);
  font-size: 12px;
}
.keyword-row__badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--status-green) 20%, transparent);
  color: var(--status-green);
}
.keyword-row__badge--off {
  background: color-mix(in srgb, var(--status-red) 20%, transparent);
  color: var(--status-red);
}
.keyword-row__time {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}
</style>