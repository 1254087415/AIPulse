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
import { computed } from 'vue'
import StatusBadge from '../ui/StatusBadge.vue'
import AppButton from '../ui/AppButton.vue'
import { formatDateTime, formatInterval } from '../../lib/format'
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

const onRemove = (): void => emit('remove', props.followed.id)
const onSync = (): void => emit('sync', props.followed.id)
const onEdit = (): void => emit('edit', props.followed.id)
</script>

<template>
  <article class="follow-card" :class="{ 'is-paused': !followed.is_active }">
    <div class="follow-card__avatar" aria-hidden="true">
      <img
        v-if="followed.profile_url"
        :src="followed.profile_url"
        :alt="followed.display_name"
        class="follow-card__avatar-img"
        loading="lazy"
        @error="($event.target as HTMLImageElement).style.display = 'none'"
      />
      <span v-else class="follow-card__avatar-initial">{{ avatarInitial }}</span>
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
        data-testid="last-error"
        role="alert"
      >
        {{ followed.last_error }}
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
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.follow-card__avatar-initial {
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

.follow-card__detail-link {
  display: inline-block;
  padding: 6px 12px;
  border: 1px solid var(--accent-coral);
  border-radius: var(--radius-sm);
  color: var(--accent-coral);
  font-size: 12px;
  text-align: center;
  text-decoration: none;
}

.follow-card__detail-link:hover {
  background: color-mix(in srgb, var(--accent-coral) 10%, transparent);
}
</style>