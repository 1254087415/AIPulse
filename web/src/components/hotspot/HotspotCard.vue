<script setup lang="ts">
import type { Hotspot } from '../../types'

function formatDate(value: string | null): string {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN')
}

const props = defineProps<{ hotspot: Hotspot }>()
</script>

<template>
  <article class="card">
    <div class="header">
      <a :href="props.hotspot.url" target="_blank" rel="noopener noreferrer" class="title">
        {{ props.hotspot.title }}
      </a>
      <span class="score">{{ props.hotspot.heat_score.toFixed(1) }}</span>
    </div>
    <p v-if="props.hotspot.summary" class="summary">{{ props.hotspot.summary }}</p>

    <div class="meta">
      <span class="source">{{ props.hotspot.source_type }}</span>
      <span v-if="props.hotspot.category" class="category">{{ props.hotspot.category }}</span>
      <span class="importance">{{ props.hotspot.importance }}</span>
      <span v-if="props.hotspot.published_at" class="date">{{ formatDate(props.hotspot.published_at) }}</span>
    </div>
  </article>
</template>

<style scoped>
.card {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 1rem;
  margin-bottom: 0.75rem;
  background: #ffffff;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}
.title {
  font-weight: 600;
  color: #111827;
  text-decoration: none;
}
.title:hover {
  text-decoration: underline;
}
.score {
  flex-shrink: 0;
  font-weight: 700;
  color: #dc2626;
}
.summary {
  color: #4b5563;
  margin: 0.5rem 0 0;
  font-size: 0.875rem;
}
.meta {
  margin-top: 0.75rem;
  display: flex;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: #6b7280;
}
.source, .category, .importance {
  text-transform: uppercase;
  letter-spacing: 0.025em;
}
</style>
