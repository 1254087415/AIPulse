<script setup lang="ts">
/**
 * DigestsView — reads the real `/api/digests` list.
 *
 * Spec §6.14 / §8.1. Rich digest preview lands in a later phase; this
 * minimal view exists so the route resolves, real data renders, and the
 * console stays clean.
 */
import { onMounted, ref } from 'vue'
import PageHeader from '../components/ui/PageHeader.vue'
import { apiFetch } from '../lib/apiFetch'
import { formatDateTime } from '../lib/format'

interface Digest {
  id: string
  title?: string | null
  created_at?: string | null
  summary?: string | null
}

const digests = ref<Digest[]>([])
const loading = ref(false)
const errorMessage = ref('')

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await apiFetch<{ success: boolean; data: Digest[] }>('/api/digests')
    digests.value = response.data
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="digests-view" data-testid="digests-view">
    <PageHeader title="摘要" subtitle="已生成的视频摘要" />

    <p v-if="loading" class="state-line" data-testid="loading">加载中…</p>
    <p v-else-if="errorMessage" class="state-line state-error" data-testid="error">
      加载失败：{{ errorMessage }}
    </p>
    <p v-else-if="digests.length === 0" class="state-line" data-testid="empty">
      暂无摘要
    </p>

    <ul v-else class="digest-list" data-testid="digest-list">
      <li v-for="d in digests" :key="d.id" class="digest-row">
        <h3 class="digest-row__title">{{ d.title || d.id }}</h3>
        <p v-if="d.summary" class="digest-row__summary">{{ d.summary }}</p>
        <span class="digest-row__time">{{ formatDateTime(d.created_at) }}</span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.digests-view {
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
.digest-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.digest-row {
  padding: 12px 14px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}
.digest-row__title {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
}
.digest-row__summary {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.digest-row__time {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
}
</style>