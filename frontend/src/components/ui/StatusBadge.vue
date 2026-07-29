<script setup lang="ts">
withDefaults(defineProps<{
  tone?: 'success' | 'warning' | 'danger' | 'neutral'
  label?: string
}>(), {
  tone: 'neutral',
  label: '',
})
</script>

<template>
  <span class="status-badge" :class="`status-badge--${tone}`" role="status">
    <slot>{{ label }}</slot>
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
  color: var(--badge-color);
  background: color-mix(in srgb, var(--badge-color) 12%, transparent);
}

.status-badge--success {
  --badge-color: var(--status-green);
}

.status-badge--warning {
  --badge-color: var(--status-amber);
}

.status-badge--danger {
  --badge-color: var(--status-red);
}

.status-badge--neutral {
  --badge-color: var(--text-secondary);
}
</style>
