<script setup lang="ts">
/**
 * HealthDot — single coloured status dot (spec §Q20 健康状态徽章).
 *
 * Three tiers:
 *   healthy → 🟢 green
 *   warning → 🟡 amber
 *   error   → 🔴 red
 *
 * Color values resolve through `--state-healthy/--state-warning/--state-error`
 * tokens (see `sidebar.css`) so themes stay consistent across views.
 */
import { computed } from 'vue'

type Status = 'healthy' | 'warning' | 'error'

interface Props {
  status: Status | string
  /** Override default 10px diameter. */
  size?: number
}

const props = withDefaults(defineProps<Props>(), {
  size: 10,
})

const normalised = computed<Status>(() => {
  if (props.status === 'healthy' || props.status === 'warning' || props.status === 'error') {
    return props.status
  }
  return 'warning'
})

const tokenVar = computed(() => {
  switch (normalised.value) {
    case 'healthy':
      return 'var(--state-healthy, #16a34a)'
    case 'warning':
      return 'var(--state-warning, #d97706)'
    case 'error':
      return 'var(--state-error, #ef4444)'
  }
})

const labelText = computed(() => {
  switch (normalised.value) {
    case 'healthy':
      return '健康'
    case 'warning':
      return '注意'
    case 'error':
      return '异常'
  }
})
</script>

<template>
  <span
    class="health-dot"
    :data-status="normalised"
    data-testid="health-dot"
    role="img"
    :aria-label="`健康状态：${labelText}`"
    :style="{ width: `${size}px`, height: `${size}px`, backgroundColor: tokenVar }"
  />
</template>

<style scoped>
.health-dot {
  display: inline-block;
  border-radius: 50%;
  flex-shrink: 0;
  vertical-align: middle;
}
</style>
