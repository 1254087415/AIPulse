<script setup lang="ts">
/**
 * HealthBadge — visual indicator for the health status of a followed UP.
 *
 * Three variants (healthy / warning / error) map to the spec §6.7 semantics:
 *  - healthy  → last scan inside the freshness window
 *  - warning  → scan lagging, or polling frequency below expected
 *  - error    → last error or failed_at populated
 *
 * Rendered both inline (compact) and as a labeled chip so the same component
 * fits inside FollowCard headers and on the FollowDetail meta grid.
 */

import { computed } from 'vue'

type HealthStatus = 'healthy' | 'warning' | 'error'

interface Props {
  status: HealthStatus
  /** Strip the text label, keep only the colored dot. */
  compact?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  compact: false,
})

interface VariantMeta {
  ariaLabel: string
  defaultText: string
  cssClass: string
}

const VARIANTS: Record<HealthStatus, VariantMeta> = {
  healthy: {
    ariaLabel: '运行正常',
    defaultText: '健康',
    cssClass: 'health-badge--healthy',
  },
  warning: {
    ariaLabel: '需要关注',
    defaultText: '关注',
    cssClass: 'health-badge--warning',
  },
  error: {
    ariaLabel: '出现异常',
    defaultText: '异常',
    cssClass: 'health-badge--error',
  },
}

const variant = computed<VariantMeta>(() => VARIANTS[props.status])

const ariaLabel = computed(() => variant.value.ariaLabel)
</script>

<template>
  <span
    class="health-badge"
    :class="[
      variant.cssClass,
      { 'health-badge--compact': compact },
    ]"
    :aria-label="ariaLabel"
    role="status"
  >
    <span class="health-badge__dot" aria-hidden="true" />
    <span v-if="!compact" class="health-badge__label">
      <slot name="label">{{ variant.defaultText }}</slot>
    </span>
  </span>
</template>

<style scoped>
.health-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  background: color-mix(in srgb, currentColor 12%, transparent);
  color: var(--badge-fg, var(--text-secondary));
  line-height: 1.4;
}

.health-badge--compact {
  padding: 0;
  background: transparent;
}

.health-badge__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 0 2px color-mix(in srgb, currentColor 25%, transparent);
  flex-shrink: 0;
}

.health-badge__label {
  text-transform: uppercase;
  font-variant-numeric: tabular-nums;
}

.health-badge--healthy {
  --badge-fg: var(--status-green, #22c55e);
}

.health-badge--warning {
  --badge-fg: var(--status-amber, #f59e0b);
}

.health-badge--error {
  --badge-fg: var(--status-red, #ef4444);
}
</style>