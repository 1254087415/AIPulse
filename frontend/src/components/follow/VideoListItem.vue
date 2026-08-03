<script setup lang="ts">
/**
 * VideoListItem — single video row used inside FollowDetailView (spec §6.12).
 *
 * The row shows: bvid + title + status badge, plus a「在 B 站打开」button
 * that emits `open-bilibili` with the bvid. The two variants are
 *
 *   - ``default`` — used inside the main recent-videos list
 *   - ``orphan``  — used inside the 散落视频 section (visually muted)
 *
 * The component is purely presentational: it does not own any data fetching
 * or mutation. The SummarizeButton (spec §6.13) is wired next to the
 * open-in-bilibili link and manages its own SSE state.
 */
import { computed } from 'vue'
import { formatStatusLabel } from '../../lib/format'
import SummarizeButton from '../buttons/SummarizeButton.vue'

export interface VideoListItemVideo {
  bvid: string
  title: string
  collection_id?: string | null
  status: string
  published_at?: string | null
  hotspot_id?: string
}

interface Props {
  video: VideoListItemVideo
  variant?: 'default' | 'orphan'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
})

const emit = defineEmits<{
  (e: 'open-bilibili', bvid: string): void
}>()

const bilibiliUrl = computed(() => `https://www.bilibili.com/video/${props.video.bvid}`)

function onOpenBilibili(event: MouseEvent) {
  // Honor cmd/ctrl-click → let the browser open the link itself
  if (event.metaKey || event.ctrlKey) return
  event.preventDefault()
  emit('open-bilibili', props.video.bvid)
}

const isOrphan = computed(() => props.variant === 'orphan')
</script>

<template>
  <li
    class="video-list-item"
    :class="{ 'video-list-item--orphan': isOrphan }"
    :data-variant="variant"
    data-testid="video-list-item"
  >
    <div class="video-list-item__body">
      <span class="video-list-item__title">{{ video.title || video.bvid }}</span>
      <code class="video-list-item__bvid">{{ video.bvid }}</code>
      <span class="video-list-item__status" :data-status="video.status">
        {{ formatStatusLabel(video.status) }}
      </span>
    </div>
    <div class="video-list-item__actions">
      <SummarizeButton :bvid="video.bvid" />
      <a
        class="video-list-item__open"
        :href="bilibiliUrl"
        target="_blank"
        rel="noopener noreferrer"
        data-testid="open-bilibili-link"
        @click="onOpenBilibili"
      >
        在 B 站打开
      </a>
    </div>
  </li>
</template>

<style scoped>
.video-list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: var(--surface-elevated, #fff);
  border: 1px solid var(--border-subtle, #e5e5e5);
  border-radius: var(--radius-sm, 6px);
  list-style: none;
}

.video-list-item--orphan {
  background: var(--surface-bg, #fafafa);
  border-style: dashed;
}

.video-list-item__body {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.video-list-item__title {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary, #1a1a1a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-list-item__bvid {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  color: var(--text-secondary, #6b6b6b);
}

.video-list-item__status {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  text-transform: lowercase;
  background: var(--surface-bg, #fafafa);
  color: var(--text-secondary, #6b6b6b);
  border: 1px solid var(--border-subtle, #e5e5e5);
}

.video-list-item__status[data-status='worth_learning'] {
  background: color-mix(in srgb, #16a34a 16%, transparent);
  color: #16a34a;
  border-color: color-mix(in srgb, #16a34a 30%, transparent);
}

.video-list-item__status[data-status='failed'] {
  background: color-mix(in srgb, var(--status-red, #ef4444) 16%, transparent);
  color: var(--status-red, #ef4444);
  border-color: color-mix(in srgb, var(--status-red, #ef4444) 30%, transparent);
}

.video-list-item__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.video-list-item__open {
  color: var(--accent-coral, #ff6a55);
  text-decoration: none;
  font-size: 13px;
  white-space: nowrap;
}

.video-list-item__open:hover {
  text-decoration: underline;
}
</style>
