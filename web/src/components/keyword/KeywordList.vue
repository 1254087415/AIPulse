<script setup lang="ts">
import type { Keyword } from '../../types'

const props = defineProps<{ keywords: Keyword[]; updating?: Record<string, boolean> }>()
const emit = defineEmits<{
  (e: 'toggleNotify', keyword: Keyword): void
  (e: 'toggleActive', keyword: Keyword): void
  (e: 'delete', keyword: Keyword): void
}>()

function confirmDelete(keyword: Keyword) {
  if (window.confirm(`确定要删除关键词“${keyword.value}”吗？`)) {
    emit('delete', keyword)
  }
}
</script>

<template>
  <ul class="keyword-list" role="list">
    <li v-for="keyword in props.keywords" :key="keyword.id" class="keyword panel">
      <div class="keyword-main">
        <span class="keyword-value" :class="{ inactive: !keyword.is_active }">
          {{ keyword.value }}
        </span>
        <span v-if="keyword.notify_on_match" class="tag tag-signal">通知</span>
        <span v-else class="tag">静默</span>
      </div>
      <div class="keyword-actions">
        <button
          type="button"
          class="action focus-ring"
          :disabled="updating?.[keyword.id]"
          :aria-label="`${keyword.notify_on_match ? '关闭' : '开启'} 关键词 ${keyword.value} 的通知`"
          @click="emit('toggleNotify', keyword)"
        >
          {{ keyword.notify_on_match ? '关闭通知' : '开启通知' }}
        </button>
        <button
          type="button"
          class="action focus-ring"
          :disabled="updating?.[keyword.id]"
          :aria-label="`${keyword.is_active ? '停用' : '启用'} 关键词 ${keyword.value}`"
          @click="emit('toggleActive', keyword)"
        >
          {{ keyword.is_active ? '停用' : '启用' }}
        </button>
        <button
          type="button"
          class="action action-danger focus-ring"
          :disabled="updating?.[keyword.id]"
          :aria-label="`删除关键词 ${keyword.value}`"
          @click="confirmDelete(keyword)"
        >
          删除
        </button>
      </div>
    </li>
  </ul>
</template>

<style scoped>
.keyword-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.keyword {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

.keyword:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.keyword-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.keyword-value {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 500;
}

.keyword-value.inactive {
  color: var(--slate);
  text-decoration: line-through;
}

.keyword-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.action {
  appearance: none;
  background: transparent;
  border: none;
  font-size: 12px;
  color: var(--slate);
  padding: 4px 6px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color 0.12s ease, background 0.12s ease;
}

.action:hover:not(:disabled) {
  color: var(--ink);
  background: rgba(27, 26, 23, 0.04);
}

.action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-danger:hover:not(:disabled) {
  color: var(--signal);
  background: var(--signal-soft);
}

@media (max-width: 640px) {
  .keyword {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .keyword-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
