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
import HealthBadge from '../health-badge/HealthBadge.vue'
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

const lastCheckedLabel = computed(() => {
  if (!props.followed.last_checked_at) return '尚未扫描'
  return new Date(props.followed.last_checked_at).toLocaleString('zh-CN')
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
        <h3 class="follow-card__name">{{ followed.display_name || followed.uid }}</h3>
        <span class="follow-card__uid">uid: {{ followed.uid }}</span>
      </header>

      <div class="follow-card__meta">
        <span class="follow-card__chip follow-card__chip--platform">{{ platformLabel }}</span>
        <span class="follow-card__chip follow-card__chip--status">{{ statusLabel }}</span>
        <slot name="health">
          <HealthBadge :status="followed.health" compact />
        </slot>
      </div>

      <p class="follow-card__line">
        <span class="follow-card__label">上次同步</span>
        <time :datetime="followed.last_checked_at ?? ''">{{ lastCheckedLabel }}</time>
        <span class="follow-card__sep">·</span>
        <span>{{ followed.fetch_interval_minutes }} 分钟 / 次</span>
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
      <button
        type="button"
        class="follow-card__btn"
        data-testid="sync-button"
        @click="onSync"
      >
        立即同步
      </button>
      <button
        type="button"
        class="follow-card__btn"
        data-testid="edit-button"
        @click="onEdit"
      >
        编辑
      </button>
      <button
        type="button"
        class="follow-card__btn follow-card__btn--danger"
        data-testid="remove-button"
        @click="onRemove"
      >
        删除
      </button>
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

.follow-card__uid {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
}

.follow-card__meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.follow-card__chip {
  font-size: 11px;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface-bg);
  color: var(--text-secondary);
  font-weight: 500;
}

.follow-card__chip--platform {
  background: color-mix(in srgb, var(--accent-coral) 10%, transparent);
  color: var(--accent-coral);
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

.follow-card__btn {
  appearance: none;
  background: var(--surface-bg);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 12px;
  padding: 6px 12px;
  cursor: pointer;
  transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease;
}

.follow-card__btn:hover {
  background: var(--surface-elevated-hover);
  border-color: var(--text-secondary);
}

.follow-card__btn--danger {
  color: var(--status-red);
  border-color: color-mix(in srgb, var(--status-red) 25%, transparent);
}

.follow-card__btn--danger:hover {
  background: var(--status-red);
  color: var(--surface-elevated);
  border-color: var(--status-red);
}
</style>