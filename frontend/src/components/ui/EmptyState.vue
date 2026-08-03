<script setup lang="ts">
import AppButton from './AppButton.vue'

withDefaults(defineProps<{
  title: string
  description: string
  actionLabel?: string
  actionHref?: string
  compact?: boolean
}>(), {
  actionLabel: undefined,
  actionHref: undefined,
  compact: false,
})
</script>

<template>
  <div
    class="empty-state"
    :class="{ 'empty-state--compact': compact }"
    data-testid="empty-state"
    :role="compact ? undefined : 'status'"
  >
    <svg
      class="empty-state__icon"
      data-testid="empty-state-icon"
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
    >
      <path d="M5 7.5h14v10H5z" stroke="currentColor" stroke-width="1.5" />
      <path d="M8 11h8M8 14h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    </svg>
    <strong class="empty-state__title" data-testid="empty-state-title">{{ title }}</strong>
    <p class="empty-state__description" data-testid="empty-state-description">{{ description }}</p>
    <AppButton
      v-if="actionLabel && actionHref"
      as="a"
      variant="secondary"
      size="sm"
      :href="actionHref"
    >
      {{ actionLabel }}
    </AppButton>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 24px;
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-md);
  background: var(--surface-elevated);
  color: var(--text-secondary);
  text-align: center;
}

.empty-state--compact {
  align-items: flex-start;
  padding: 14px;
  text-align: left;
}

.empty-state__icon {
  width: 28px;
  height: 28px;
  color: var(--text-secondary);
  opacity: 0.7;
}

.empty-state--compact .empty-state__icon {
  width: 22px;
  height: 22px;
}

.empty-state__title {
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 600;
}

.empty-state__description {
  max-width: 440px;
  margin: 0;
  font-size: var(--text-sm);
  line-height: 1.5;
}
</style>
