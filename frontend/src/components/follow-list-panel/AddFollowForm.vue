<script setup lang="ts">
/**
 * AddFollowForm — minimal form to add a new followed UP主.
 *
 * Validates that `uid` is non-empty before emitting `submit`. The parent
 * (FollowListPanel) owns the API call and the error feedback loop.
 */
import { computed, ref } from 'vue'
import type { FollowedUpCreate, FollowedUpPlatform } from '../../api/followedUp'

interface Props {
  submitting: boolean
  errorMessage?: string | null
}

withDefaults(defineProps<Props>(), {
  errorMessage: null,
})

const emit = defineEmits<{
  (e: 'submit', payload: FollowedUpCreate): void
  (e: 'cancel'): void
}>()

const PLATFORM_OPTIONS: FollowedUpPlatform[] = [
  'bilibili',
  'wechat_mp',
  'douyin',
  'xiaohongshu',
]

const PLATFORM_LABELS: Record<FollowedUpPlatform, string> = {
  bilibili: 'B 站',
  wechat_mp: '公众号',
  douyin: '抖音',
  xiaohongshu: '小红书',
}

const platform = ref<FollowedUpPlatform>('bilibili')
const uid = ref<string>('')

const isValid = computed<boolean>(() => uid.value.trim().length > 0)

const onSubmit = (event: Event): void => {
  event.preventDefault()
  if (!isValid.value) return
  emit('submit', {
    platform: platform.value,
    uid: uid.value.trim(),
  })
}

const onCancel = (): void => emit('cancel')
</script>

<template>
  <form class="add-follow-form" @submit="onSubmit">
    <div class="add-follow-form__row">
      <label class="add-follow-form__field">
        <span class="add-follow-form__label">平台</span>
        <select
          v-model="platform"
          class="add-follow-form__select"
          data-testid="platform-select"
          :disabled="submitting"
        >
          <option v-for="opt in PLATFORM_OPTIONS" :key="opt" :value="opt">
            {{ PLATFORM_LABELS[opt] }}
          </option>
        </select>
      </label>

      <label class="add-follow-form__field add-follow-form__field--grow">
        <span class="add-follow-form__label">UP 主 UID / mid</span>
        <input
          v-model="uid"
          class="add-follow-form__input"
          data-testid="uid-input"
          type="text"
          placeholder="例如 1567748478"
          :disabled="submitting"
        />
      </label>
    </div>

    <p
      v-if="errorMessage"
      class="add-follow-form__error"
      data-testid="form-error"
      role="alert"
    >
      {{ errorMessage }}
    </p>

    <div class="add-follow-form__actions">
      <button
        type="button"
        class="add-follow-form__btn add-follow-form__btn--ghost"
        data-testid="cancel-button"
        :disabled="submitting"
        @click="onCancel"
      >
        取消
      </button>
      <button
        type="submit"
        class="add-follow-form__btn add-follow-form__btn--primary"
        data-testid="submit-button"
        :disabled="submitting || !isValid"
      >
        {{ submitting ? '添加中…' : '添加' }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.add-follow-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}

.add-follow-form__row {
  display: flex;
  gap: 12px;
  align-items: stretch;
}

.add-follow-form__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 0 0 140px;
}

.add-follow-form__field--grow {
  flex: 1;
}

.add-follow-form__label {
  font-size: 11px;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.add-follow-form__select,
.add-follow-form__input {
  appearance: none;
  height: 36px;
  padding: 0 10px;
  background: var(--surface-bg);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 14px;
  font-family: var(--font-body);
}

.add-follow-form__select:focus,
.add-follow-form__input:focus {
  outline: none;
  border-color: var(--accent-coral);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent-coral) 20%, transparent);
}

.add-follow-form__error {
  margin: 0;
  padding: 6px 10px;
  background: color-mix(in srgb, var(--status-red) 12%, transparent);
  border-radius: var(--radius-sm);
  color: var(--status-red);
  font-size: 12px;
}

.add-follow-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.add-follow-form__btn {
  appearance: none;
  height: 36px;
  padding: 0 16px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 150ms ease, color 150ms ease;
}

.add-follow-form__btn--ghost {
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
}

.add-follow-form__btn--ghost:hover:not(:disabled) {
  background: var(--surface-elevated-hover);
  color: var(--text-primary);
}

.add-follow-form__btn--primary {
  background: var(--accent-coral);
  border: 1px solid var(--accent-coral);
  color: var(--surface-elevated);
}

.add-follow-form__btn--primary:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent-coral) 88%, black);
}

.add-follow-form__btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>