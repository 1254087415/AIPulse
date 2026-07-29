<script setup lang="ts">
/**
 * FollowCard — single UP主 card (spec §6.7).
 *
 * Renders the 7 fields required by the spec:
 *   头像 / 名称 / 平台 / 状态 / 健康徽章 / 上次同步 / 错误信息
 *
 * All mutating actions are emitted up to the parent (the list panel), which
 * owns the API calls and the optimistic update flow.
 */
import { computed, ref } from 'vue'
import StatusBadge from '../ui/StatusBadge.vue'
import AppButton from '../ui/AppButton.vue'
import { formatDateTime, formatInterval } from '../../lib/format'
import { summarizeError } from '../../lib/errorMessage'
import type { FollowedUp } from '../../api/followedUp'

interface Props {
  followed: FollowedUp
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'remove', id: string): void
  (e: 'sync', id: string): void
  (e: 'edit', id: string): void
}>()

const PLATFORM_LABELS: Record<string, string> = {
  bilibili: 'B 站',
  wechat_mp: '公众号',
  douyin: '抖音',
  xiaohongshu: '小红书',
}

const platformLabel = computed(() => PLATFORM_LABELS[props.followed.platform] ?? props.followed.platform)
const statusLabel = computed(() => (props.followed.is_active ? '启用' : '已暂停'))
const healthBadge = computed(() => ({
  healthy: { label: '健康', tone: 'success' as const },
  warning: { label: '关注', tone: 'warning' as const },
  error: { label: '异常', tone: 'danger' as const },
})[props.followed.health])

const lastCheckedLabel = computed(() => {
  if (!props.followed.last_checked_at) return '尚未扫描'
  return formatDateTime(props.followed.last_checked_at)
})

const avatarInitial = computed(() => {
  const name = props.followed.display_name ?? ''
  return name.slice(0, 1) || '?'
})

// Avatar URL priority: cached B站 avatar (config.avatar_url, populated by
// opening the detail page — see backend fix in 68ced3c) → profile_url.
// profile_url defaults to the user space URL when the user adds the UP, which
// is not a valid image src; we fall back to the initial letter when image
// load fails.
const cachedAvatarUrl = computed<string | null>(() => {
  const cfg = props.followed.config
  if (cfg && typeof cfg === 'object' && typeof cfg.avatar_url === 'string') {
    return cfg.avatar_url
  }
  return null
})

const avatarUrl = computed<string | null>(() => cachedAvatarUrl.value ?? props.followed.profile_url ?? null)

const imageFailed = ref(false)
const showImage = computed(() => !!avatarUrl.value && !imageFailed.value)

const onAvatarError = (): void => {
  imageFailed.value = true
}

const lastErrorSummary = computed(() => summarizeError(props.followed.last_error))

const onRemove = (): void => emit('remove', props.followed.id)
const onSync = (): void => emit('sync', props.followed.id)
const onEdit = (): void => emit('edit', props.followed.id)
</script>

<template>
  <article class="follow-card" :class="{ 'is-paused': !followed.is_active }">
    <div class="follow-card__avatar" aria-hidden="true">
      <img
        v-if="showImage"
        :src="avatarUrl ?? ''"
        :alt="followed.display_name"
        class="follow-card__avatar-img"
        loading="lazy"
        referrerpolicy="no-referrer"
        @error="onAvatarError"
      />
      <span class="follow-card__avatar-initial">{{ avatarInitial }}</span>
    </div>

    <div class="follow-card__body">
      <header class="follow-card__header">
        <h3 class="follow-card__name" :title="followed.uid">{{ followed.display_name || followed.uid }}</h3>
      </header>

      <div class="follow-card__meta">
        <StatusBadge tone="warning" :label="platformLabel" />
        <StatusBadge :tone="followed.is_active ? 'success' : 'neutral'" :label="statusLabel" />
        <slot name="health">
          <StatusBadge :tone="healthBadge.tone" :label="healthBadge.label" />
        </slot>
      </div>

      <p class="follow-card__line">
        <span class="follow-card__label">上次同步</span>
        <time :datetime="followed.last_checked_at ?? ''">{{ lastCheckedLabel }}</time>
        <span class="follow-card__sep">·</span>
        <span>{{ formatInterval(followed.fetch_interval_minutes) }}</span>
      </p>

      <p
        v-if="followed.last_error"
        class="follow-card__error"
        :title="lastErrorSummary.technical ?? followed.last_error"
        data-testid="last-error"
        role="alert"
      >
        {{ lastErrorSummary.summary }}
      </p>
    </div>

    <div class="follow-card__actions">
      <slot name="detail" />
      <AppButton
        size="sm"
        variant="secondary"
        data-testid="sync-button"
        @click="onSync"
      >
        立即同步
      </AppButton>
      <AppButton
        size="sm"
        variant="secondary"
        data-testid="edit-button"
        @click="onEdit"
      >
        编辑
      </AppButton>
      <AppButton
        size="sm"
        variant="danger"
        data-testid="remove-button"
        @click="onRemove"
      >
        删除
      </AppButton>
    </div>
  </article>
</template>

<style scoped>
.follow-card {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
  background: var(--surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  transition: border-color 150ms ease, transform 150ms ease;
}

.follow-card:hover {
  border-color: color-mix(in srgb, var(--accent-coral) 35%, var(--border-subtle));
}

.follow-card.is-paused {
  opacity: 0.6;
}

.follow-card__avatar {
  position: relative;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--accent-coral) 18%, var(--surface-bg));
  color: var(--accent-coral);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
  font-weight: 700;
  font-family: var(--font-display);
}

.follow-card__avatar-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 1;
}

.follow-card__avatar-initial {
  position: relative;
  z-index: 0;
  font-size: 18px;
}

.follow-card__body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.follow-card__header {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.follow-card__name {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.follow-card__meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.follow-card__line {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.follow-card__label {
  color: var(--text-secondary);
  letter-spacing: 0.02em;
}

.follow-card__sep {
  color: var(--border-subtle);
}

.follow-card__error {
  margin: 0;
  padding: 6px 10px;
  background: color-mix(in srgb, var(--status-red) 12%, transparent);
  border-radius: var(--radius-sm);
  color: var(--status-red);
  font-size: 12px;
  font-weight: 500;
}

.follow-card__actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: stretch;
}
</style>