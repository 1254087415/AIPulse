<script setup lang="ts">
/**
 * AppButton — single source of truth for buttons across the dashboard.
 *
 * Variants (audit report M1):
 *   primary   — orange filled; main action on a page (add / save / submit)
 *   secondary — outlined grey; second-tier actions (refresh / sync / edit)
 *   danger    — red outline; destructive actions (delete / remove)
 *   ghost     — transparent borderless; inline / tertiary (cancel / toggle)
 *
 * Sizes:
 *   sm        — compact, dense rows (icon-like)
 *   md        — default; matches existing 32–40px button height
 *
 * Pass any native <button> attrs through (`type`, `disabled`, `data-testid`,
 * `@click`, etc.). The component renders a `<button>` by default; pass
 * `as="a"` to render an anchor instead for navigation actions.
 */
import { computed } from 'vue'

interface Props {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md'
  /** Render full-width (e.g. settings save button). */
  block?: boolean
  /** Render as an anchor for navigation actions. */
  as?: 'button' | 'a'
  href?: string
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'secondary',
  size: 'md',
  block: false,
  as: 'button',
  href: undefined,
  type: 'button',
  disabled: false,
  loading: false,
})

const classes = computed(() => [
  'app-button',
  `app-button--${props.variant}`,
  `app-button--${props.size}`,
  {
    'app-button--block': props.block,
    'app-button--loading': props.loading,
  },
])
</script>

<template>
  <button
    v-if="as === 'button'"
    :class="classes"
    :type="type"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
  >
    <slot />
  </button>
  <a
    v-else
    :class="classes"
    :href="disabled || loading ? undefined : href"
    :aria-disabled="disabled || loading ? 'true' : undefined"
    :tabindex="disabled || loading ? -1 : undefined"
    role="button"
  >
    <slot />
  </a>
</template>

<style scoped>
.app-button {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-family: var(--font-body);
  font-weight: 500;
  line-height: 1;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  cursor: pointer;
  user-select: none;
  transition:
    background-color 150ms ease,
    color 150ms ease,
    border-color 150ms ease,
    transform 80ms ease;
  text-decoration: none;
  white-space: nowrap;
}

.app-button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent-coral) 25%, transparent);
}

.app-button:disabled,
.app-button[aria-disabled='true'] {
  opacity: 0.55;
  cursor: not-allowed;
  pointer-events: none;
}

.app-button:active:not(:disabled):not([aria-disabled='true']) {
  transform: translateY(0.5px);
}

.app-button--sm {
  height: 28px;
  padding: 0 10px;
  font-size: 12px;
}

.app-button--md {
  height: 36px;
  padding: 0 16px;
  font-size: 13px;
}

.app-button--block {
  width: 100%;
}

.app-button--primary {
  background: var(--accent-coral);
  border-color: var(--accent-coral);
  color: var(--surface-elevated);
}

.app-button--primary:hover:not(:disabled):not([aria-disabled='true']) {
  background: color-mix(in srgb, var(--accent-coral) 88%, black);
  border-color: color-mix(in srgb, var(--accent-coral) 88%, black);
}

.app-button--secondary {
  background: var(--surface-elevated);
  border-color: var(--border-subtle);
  color: var(--text-primary);
}

.app-button--secondary:hover:not(:disabled):not([aria-disabled='true']) {
  background: var(--surface-elevated-hover);
  border-color: var(--text-secondary);
}

.app-button--danger {
  background: transparent;
  border-color: color-mix(in srgb, var(--status-red) 35%, transparent);
  color: var(--status-red);
}

.app-button--danger:hover:not(:disabled):not([aria-disabled='true']) {
  background: var(--status-red);
  border-color: var(--status-red);
  color: var(--surface-elevated);
}

.app-button--ghost {
  background: transparent;
  border-color: transparent;
  color: var(--text-secondary);
}

.app-button--ghost:hover:not(:disabled):not([aria-disabled='true']) {
  background: var(--surface-elevated-hover);
  color: var(--text-primary);
}

@media (prefers-reduced-motion: reduce) {
  .app-button {
    transition: none;
  }

  .app-button:active:not(:disabled):not([aria-disabled='true']) {
    transform: none;
  }
}
</style>