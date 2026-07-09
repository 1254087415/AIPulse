<script setup lang="ts">
import type { Keyword } from '../../types'

const props = defineProps<{ keywords: Keyword[] }>()
</script>

<template>
  <ul class="keyword-list">
    <li v-for="keyword in props.keywords" :key="keyword.id" class="keyword">
      {{ keyword.value }}
      <span v-if="keyword.notify_on_match" class="badge">通知</span>
    </li>
  </ul>
</template>

<style scoped>
.keyword-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.keyword {
  padding: 0.5rem 0;
  border-bottom: 1px solid #e5e7eb;
}
.badge {
  margin-left: 0.5rem;
  font-size: 0.75rem;
  color: #2563eb;
  background: #eff6ff;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
}
</style>
