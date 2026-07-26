<script setup lang="ts">
/**
 * AddFollowForm — single textbox that accepts a B站 profile URL (spec §6.6).
 *
 * The form resolves the URL to (platform=bilibili, uid=mid) before emitting
 * `submit`. The parent (FollowListPanel) owns the API call. Spec §1.3 lists
 * WechatMP / Douyin / Xiaohongshu as out of scope, so the platform dropdown
 * has been removed; only B站 is supported in v0.3.
 */
import { computed, ref } from 'vue'
import type { FollowedUpCreate } from '../../api/followedUp'

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

// Matches either a full B站 profile URL or a bare numeric mid.
const BILIBILI_MID_PATTERN = /^\d+$/
const BILIBILI_SPACE_URL_PATTERN = /space\.bilibili\.com\/(\d+)/

function extractBilibiliMid(raw: string): string | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  if (BILIBILI_MID_PATTERN.test(trimmed)) return trimmed
  const match = BILIBILI_SPACE_URL_PATTERN.exec(trimmed)
  return match?.[1] ?? null
}

const urlInput = ref<string>('')
const resolvedUid = ref<string | null>(null)

const isValidUrl = computed<boolean>(() => extractBilibiliMid(urlInput.value) !== null)
const isNonBilibiliHint = computed<boolean>(
  () => urlInput.value.trim().length > 0 && !isValidUrl.value,
)

const onSubmit = (event: Event): void => {
  event.preventDefault()
  if (!isValidUrl.value) return
  const uid = extractBilibiliMid(urlInput.value)
  if (!uid) return
  emit('submit', {
    platform: 'bilibili',
    uid,
  })
}

const onCancel = (): void => emit('cancel')
</script>

<template>
  <form class="add-follow-form" @submit="onSubmit">
    <label class="add-follow-form__field">
      <span class="add-follow-form__label">B 站主页链接</span>
      <input
        v-model="urlInput"
        class="add-follow-form__input"
        data-testid="url-input"
        type="text"
        placeholder="例如 https://space.bilibili.com/1567748478"
        :disabled="submitting"
      />
      <span
        v-if="isNonBilibiliHint"
        class="add-follow-form__hint"
        data-testid="url-hint"
        role="alert"
      >
        请粘贴 B 站主页链接（如 https://space.bilibili.com/1567748478）
      </span>
    </label>

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
        :disabled="submitting || !isValidUrl"
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

.add-follow-form__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.add-follow-form__label {
  font-size: 11px;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  text-transform: uppercase;
}

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

.add-follow-form__input:focus {
  outline: none;
  border-color: var(--accent-coral);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent-coral) 20%, transparent);
}

.add-follow-form__hint {
  font-size: 12px;
  color: var(--status-red);
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