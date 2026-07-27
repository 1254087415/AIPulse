<script setup lang="ts">
import type { FollowedUpHealth, FollowedUpStatus } from '../../types'

const props = defineProps<{ health: FollowedUpHealth; status: FollowedUpStatus }>()

const label = (): string => {
  if (props.status === 'auth_failed') return '登录态失效'
  if (props.health === 'error') return '采集失败'
  if (props.health === 'warning') return '需关注'
  return '健康'
}
</script>

<template>
  <span class="badge" :data-health="health" :data-status="status" :aria-label="`健康度 ${label()}`">
    {{ label() }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid var(--mist);
  background: var(--color-surface, #fff);
  color: var(--slate);
}

.badge[data-health='healthy'] {
  color: var(--signal);
  border-color: var(--signal);
}

.badge[data-health='warning'] {
  color: #b76b00;
  border-color: #b76b00;
}

.badge[data-health='error'],
.badge[data-status='auth_failed'] {
  color: #c2410c;
  border-color: #c2410c;
}
</style>