<script setup lang="ts">
/**
 * ConfirmModal — simple two-button modal used for destructive actions
 * (e.g. UP主删除，spec §6.12).
 *
 * Rendered via `v-if` rather than the native <dialog> API so jsdom tests can
 * drive it without a polyfill for `HTMLDialogElement.showModal`. Pressing
 * Escape emits `cancel` via the document-level keydown handler.
 *
 * `testIdPrefix` lets the parent scope the data-testid attributes (e.g.
 * `data-testid="delete-confirm"` + `data-testid="delete-confirm-confirm"`)
 * so multiple modals in the same DOM can be addressed independently in
 * tests.
 */
import { computed, onBeforeUnmount, watch } from 'vue'

interface Props {
  show: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  loading?: boolean
  danger?: boolean
  testIdPrefix?: string
}

const props = withDefaults(defineProps<Props>(), {
  confirmText: '确认',
  cancelText: '取消',
  loading: false,
  danger: false,
  testIdPrefix: 'confirm-modal',
})

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'confirm'): void
}>()

const testIds = computed(() => ({
  root: props.testIdPrefix,
  cancel: `${props.testIdPrefix}-cancel`,
  confirm: `${props.testIdPrefix}-confirm`,
}))

function onCancel() {
  if (props.loading) return
  emit('cancel')
}

function onConfirm() {
  if (props.loading) return
  emit('confirm')
}

function onKeydown(event: KeyboardEvent) {
  if (!props.show) return
  if (event.key === 'Escape') {
    event.preventDefault()
    onCancel()
  }
}

watch(
  () => props.show,
  (next) => {
    if (typeof document === 'undefined') return
    if (next) {
      document.addEventListener('keydown', onKeydown)
    } else {
      document.removeEventListener('keydown', onKeydown)
    }
  },
)

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') {
    document.removeEventListener('keydown', onKeydown)
  }
})
</script>

<template>
  <div
    v-if="show"
    class="ui-confirm-overlay"
    role="presentation"
    @click.self="onCancel"
  >
    <div
      class="ui-confirm"
      role="alertdialog"
      :aria-label="title"
      :data-testid="testIds.root"
    >
      <h2 class="ui-confirm__title">{{ title }}</h2>
      <p class="ui-confirm__message">{{ message }}</p>
      <div class="ui-confirm__actions">
        <button
          type="button"
          class="ui-confirm__btn ui-confirm__btn--ghost"
          :data-testid="testIds.cancel"
          :disabled="loading"
          @click="onCancel"
        >
          {{ cancelText }}
        </button>
        <button
          type="button"
          :class="danger ? 'ui-confirm__btn ui-confirm__btn--danger' : 'ui-confirm__btn ui-confirm__btn--primary'"
          :data-testid="testIds.confirm"
          :disabled="loading"
          @click="onConfirm"
        >
          {{ loading ? '处理中…' : confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ui-confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.ui-confirm {
  border: 1px solid var(--border-subtle, #e5e5e5);
  border-radius: var(--radius-md, 10px);
  padding: 20px 22px;
  background: var(--surface-elevated, #fff);
  color: var(--text-primary, #1a1a1a);
  min-width: 320px;
  max-width: 480px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
}

.ui-confirm__title {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 600;
}

.ui-confirm__message {
  margin: 0 0 16px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary, #555);
}

.ui-confirm__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.ui-confirm__btn {
  appearance: none;
  border: 1px solid var(--border-subtle, #e5e5e5);
  border-radius: var(--radius-sm, 6px);
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  background: var(--surface-elevated, #fff);
  color: var(--text-primary, #1a1a1a);
}

.ui-confirm__btn:disabled {
  opacity: 0.55;
  cursor: default;
}

.ui-confirm__btn--primary {
  background: var(--accent-coral, #ff6a55);
  border-color: var(--accent-coral, #ff6a55);
  color: #fff;
}

.ui-confirm__btn--danger {
  background: transparent;
  border-color: color-mix(in srgb, var(--status-red, #ef4444) 30%, transparent);
  color: var(--status-red, #ef4444);
}

.ui-confirm__btn--ghost {
  background: transparent;
}
</style>
